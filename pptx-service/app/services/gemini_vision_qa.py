"""Gemini Vision QA — analyzes slide images for layout/formatting issues."""

from __future__ import annotations

import asyncio
import base64
import json
import logging
from pathlib import Path

import google.auth
import google.auth.transport.requests
import httpx

from app.config import settings
from app.utils.soffice_wrapper import LibreOfficeConverter, PdftoPpmConverter

logger = logging.getLogger(__name__)

# Issue schema that Gemini must return
_VISION_SYSTEM_PROMPT = """\
Du bist ein Experte fuer PowerPoint-Qualitaetskontrolle. Du analysierst ein Folienbild \
und findest visuelle Probleme.

Pruefe JEDE Folie auf diese Probleme — in dieser Reihenfolge:

0. CONTENT_LEAK (HOECHSTE PRIORITAET — immer severity=error!):
   - Rohe Icon-Beschreibungen als Text sichtbar (z.B. "Monastery icon", "Shield or scroll icon",
     "Hopfenpflanze", "Buch mit Feder", "Landkarte mit Pin", "Zahnrad")
   - Bildbeschreibungen/Prompts als sichtbarer Text (z.B. "photorealistic", "stock photo of...")
   - Placeholder-Texte ([placeholder], [TODO], {variable}, Lorem ipsum, XYZ, TBD)
   - AI-Generierungs-Prompts sichtbar auf der Folie
   - Technische Metadaten (Dateinamen, IDs, JSON-Fragmente)
   - "[Diagramm: ...]" oder aehnliche interne Labels
   → Wenn IRGENDEIN solches Element sichtbar ist: severity=error, fix_action=clear_content_leak

1. TEXT_OVERFLOW: Text ragt ueber den sichtbaren Bereich hinaus oder wird abgeschnitten
2. IMAGE_OVERFLOW: Bild ist zu gross, ragt ueber die Folie hinaus oder ueberlappt andere Elemente
3. IMAGE_MISSING: Leerer Bildplatzhalter oder Platzhalter-Grafik sichtbar (grauer Kasten, "Bildplatzhalter"-Text)
4. EMPTY_PLACEHOLDER: Sichtbarer Platzhaltertext wie "Titel hinzufuegen", "Text hier", "xxxx" etc.
5. OVERLAP: Elemente ueberlappen sich ungewollt (Text ueber Bild, Elemente uebereinander)
6. LOW_CONTRAST: Text ist schwer lesbar wegen zu geringem Kontrast zum Hintergrund
7. LAYOUT_BROKEN: Folie sieht strukturell falsch aus (z.B. Closing-Folie ohne Inhalt, leere Folie)
8. SPACING: Unregelmaessige oder zu enge Abstaende zwischen Elementen

Antworte NUR mit validem JSON. Keine Erklaerungen ausserhalb des JSON.
Format:
{
  "issues": [
    {
      "type": "CONTENT_LEAK|TEXT_OVERFLOW|IMAGE_OVERFLOW|IMAGE_MISSING|EMPTY_PLACEHOLDER|OVERLAP|LOW_CONTRAST|LAYOUT_BROKEN|SPACING",
      "severity": "error|warning",
      "element": "Welches Element betroffen ist (z.B. 'Titel', 'Bullet 3', 'Bild rechts')",
      "description": "Kurze Beschreibung des Problems auf Deutsch",
      "fix_action": "clear_content_leak|resize_image|crop_image|truncate_text|remove_placeholder|reposition|change_font_color|fill_content|adjust_spacing|none",
      "fix_params": {}
    }
  ],
  "overall_quality": "good|acceptable|poor",
  "slide_summary": "Ein Satz was die Folie zeigt"
}

WICHTIG: Pruefe ZUERST ob rohe Beschreibungstexte, Icon-Labels, Placeholder oder \
AI-Prompts sichtbar auf der Folie stehen — das ist der schlimmste Fehler!
Wenn die Folie keine Probleme hat, gib ein leeres issues-Array zurueck.
Sei STRENG — melde auch kleine Probleme als warnings.
"""


class SlideIssue:
    """Single issue found on a slide."""

    def __init__(self, slide_number: int, issue_type: str, severity: str,
                 element: str, description: str, fix_action: str,
                 fix_params: dict | None = None):
        self.slide_number = slide_number
        self.issue_type = issue_type
        self.severity = severity
        self.element = element
        self.description = description
        self.fix_action = fix_action
        self.fix_params = fix_params or {}

    def to_dict(self) -> dict:
        return {
            "slide_number": self.slide_number,
            "issue_type": self.issue_type,
            "severity": self.severity,
            "element": self.element,
            "description": self.description,
            "fix_action": self.fix_action,
            "fix_params": self.fix_params,
        }


class VisionQAResult:
    """Result of vision QA across all slides."""

    def __init__(self):
        self.issues: list[SlideIssue] = []
        self.slide_count: int = 0
        self.image_paths: list[str] = []
        self.error: str | None = None

    @property
    def has_fixable_issues(self) -> bool:
        return any(i.fix_action != "none" for i in self.issues)

    @property
    def error_count(self) -> int:
        return len([i for i in self.issues if i.severity == "error"])

    @property
    def warning_count(self) -> int:
        return len([i for i in self.issues if i.severity == "warning"])


def _get_access_token() -> str:
    credentials, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )
    credentials.refresh(google.auth.transport.requests.Request())
    return credentials.token


async def convert_pptx_to_images(pptx_path: str) -> list[str]:
    """Convert PPTX to slide JPEG images via LibreOffice + pdftoppm."""
    converter = LibreOfficeConverter()
    pdf_converter = PdftoPpmConverter()

    pdf_path = await converter.pptx_to_pdf(pptx_path)
    image_paths = await pdf_converter.pdf_to_jpeg(pdf_path, dpi=150)
    return image_paths


async def _analyze_single_slide(
    image_path: str,
    slide_number: int,
    token: str,
) -> list[SlideIssue]:
    """Send one slide image to Gemini Vision and parse issues."""
    with open(image_path, "rb") as f:
        image_bytes = f.read()

    image_b64 = base64.b64encode(image_bytes).decode("utf-8")

    url = (
        f"https://{settings.gcp_region}-aiplatform.googleapis.com/v1/"
        f"projects/{settings.gcp_project_id}/locations/{settings.gcp_region}/"
        f"publishers/google/models/{settings.gemini_model}:generateContent"
    )

    payload = {
        "contents": [{
            "role": "user",
            "parts": [
                {"text": f"Analysiere Folie {slide_number} dieser Praesentation auf visuelle Probleme:"},
                {
                    "inlineData": {
                        "mimeType": "image/jpeg",
                        "data": image_b64,
                    }
                },
            ],
        }],
        "systemInstruction": {
            "parts": [{"text": _VISION_SYSTEM_PROMPT}],
        },
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 2048,
            "responseMimeType": "application/json",
        },
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                url,
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
            )

        if response.status_code != 200:
            logger.warning(
                f"[Vision QA] Gemini API error for slide {slide_number}: "
                f"{response.status_code} {response.text[:200]}"
            )
            return []

        data = response.json()
        candidates = data.get("candidates", [])
        if not candidates:
            return []

        text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
        if not text:
            return []

        # Parse JSON response — handle markdown code fences
        clean_text = text.strip()
        if clean_text.startswith("```"):
            clean_text = clean_text.split("\n", 1)[-1]
            if clean_text.endswith("```"):
                clean_text = clean_text[:-3]
            clean_text = clean_text.strip()

        result = json.loads(clean_text)
        issues = []
        for item in result.get("issues", []):
            issues.append(SlideIssue(
                slide_number=slide_number,
                issue_type=item.get("type", "UNKNOWN"),
                severity=item.get("severity", "warning"),
                element=item.get("element", ""),
                description=item.get("description", ""),
                fix_action=item.get("fix_action", "none"),
                fix_params=item.get("fix_params", {}),
            ))
        return issues

    except json.JSONDecodeError as e:
        logger.warning(f"[Vision QA] JSON parse error for slide {slide_number}: {e}")
        return []
    except Exception as e:
        logger.warning(f"[Vision QA] Analysis failed for slide {slide_number}: {e}")
        return []


async def run_vision_qa(
    pptx_path: str,
    slide_indices: list[int] | None = None,
    progress_callback=None,
) -> VisionQAResult:
    """Run Gemini Vision QA on a PPTX file.

    Args:
        pptx_path: Path to the PPTX file.
        slide_indices: If set, only analyze these slide numbers (1-based).
            None means analyze all slides.
        progress_callback: Optional (step, message, progress) callback.

    Returns:
        VisionQAResult with all found issues.
    """
    result = VisionQAResult()

    try:
        if progress_callback:
            progress_callback("qa_convert", "Folien werden fuer QA konvertiert...", None)

        image_paths = await convert_pptx_to_images(pptx_path)
        result.image_paths = image_paths
        result.slide_count = len(image_paths)

        if not image_paths:
            result.error = "Keine Folienbilder erzeugt"
            return result

        token = _get_access_token()

        # Filter to specific slides if requested
        slides_to_check = []
        for idx, path in enumerate(image_paths):
            slide_num = idx + 1
            if slide_indices is None or slide_num in slide_indices:
                slides_to_check.append((slide_num, path))

        total = len(slides_to_check)
        if progress_callback:
            progress_callback(
                "qa_check",
                f"Gemini prueft {total} Folie(n)...",
                None,
            )

        # Analyze slides concurrently (max 4 parallel)
        semaphore = asyncio.Semaphore(4)

        async def analyze_with_limit(slide_num: int, path: str) -> list[SlideIssue]:
            async with semaphore:
                if progress_callback:
                    progress_callback(
                        "qa_check",
                        f"Folie {slide_num}/{result.slide_count} wird geprueft...",
                        None,
                    )
                return await _analyze_single_slide(path, slide_num, token)

        tasks = [analyze_with_limit(num, path) for num, path in slides_to_check]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for r in results:
            if isinstance(r, Exception):
                logger.warning(f"[Vision QA] Slide analysis exception: {r}")
                continue
            result.issues.extend(r)

        logger.info(
            f"[Vision QA] Complete: {result.slide_count} slides, "
            f"{result.error_count} errors, {result.warning_count} warnings"
        )

    except Exception as e:
        logger.error(f"[Vision QA] Pipeline failed: {e}")
        result.error = str(e)

    return result
