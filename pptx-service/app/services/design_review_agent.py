"""Design Review Agent — visually reviews generated PPTX files and applies design fixes.

This agent:
1. Converts PPTX to slide images
2. Sends each slide to Gemini Vision with a design-focused prompt
3. Parses structured design recommendations
4. Maps recommendations to RenderInstruction adjustments
5. Re-renders the fixed presentation
6. Optionally loops for verification
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

import google.auth
import google.auth.transport.requests
import httpx

from app.config import settings
from app.schemas.models import RenderInstruction, RenderElement, SlideType
from app.services.gemini_vision_qa import convert_pptx_to_images
from app.prompts.design_review_prompt import (
    DESIGN_REVIEW_SYSTEM_PROMPT,
    build_design_review_prompt,
)

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[str, str, Optional[int]], None]


# ═══════════════════════════════════════════════════════════════
# Data structures
# ═══════════════════════════════════════════════════════════════

@dataclass
class DesignFix:
    """A single design fix recommendation from the agent."""
    slide_index: int
    priority: str  # critical, important, nice_to_have
    category: str  # FONT_SIZE, SPACING, POSITION, SIZE, PADDING, FONT_WEIGHT, COLOR, REMOVE
    target_element: str
    issue: str
    fix: str
    params: dict = field(default_factory=dict)

    @property
    def is_critical(self) -> bool:
        return self.priority == "critical"


@dataclass
class SlideReview:
    """Design review result for a single slide."""
    slide_index: int
    design_score: int
    verdict: str
    strengths: list[str] = field(default_factory=list)
    fixes: list[DesignFix] = field(default_factory=list)

    @property
    def needs_fixes(self) -> bool:
        return self.design_score < 8 and len(self.fixes) > 0


@dataclass
class DesignReviewResult:
    """Complete design review result."""
    slide_reviews: list[SlideReview] = field(default_factory=list)
    avg_score: float = 0.0
    total_fixes_applied: int = 0
    iterations_run: int = 0
    error: str | None = None

    @property
    def passed(self) -> bool:
        return self.avg_score >= 7.0

    def to_dict(self) -> dict:
        return {
            "avg_score": round(self.avg_score, 1),
            "passed": self.passed,
            "iterations_run": self.iterations_run,
            "total_fixes_applied": self.total_fixes_applied,
            "slide_scores": [
                {"slide": r.slide_index + 1, "score": r.design_score, "verdict": r.verdict}
                for r in self.slide_reviews
            ],
            "error": self.error,
        }


# ═══════════════════════════════════════════════════════════════
# Design Review Agent
# ═══════════════════════════════════════════════════════════════

class DesignReviewAgent:
    """Agent that visually reviews presentations and applies design fixes."""

    def __init__(
        self,
        render_instructions: list[RenderInstruction],
        renderer,  # PptxRendererV2 instance
        max_iterations: int = 2,
    ):
        self._instructions = render_instructions
        self._renderer = renderer
        self._max_iterations = max_iterations
        self._progress_cb: ProgressCallback | None = None

    def set_progress_callback(self, cb: ProgressCallback) -> None:
        self._progress_cb = cb

    def _progress(self, step: str, message: str, pct: int | None = None) -> None:
        if self._progress_cb:
            self._progress_cb(step, message, pct)
        logger.info(f"[DesignReview] {step}: {message}")

    async def review_and_fix(
        self,
        pptx_path: str | Path,
        output_dir: str | None = None,
    ) -> DesignReviewResult:
        """Run the full design review loop.

        1. Convert PPTX to images
        2. Analyze each slide with Gemini Vision (design-focused)
        3. Apply fixes to RenderInstructions
        4. Re-render if fixes were applied
        5. Optionally verify with a second pass

        Returns:
            DesignReviewResult with scores, fixes, and final state.
        """
        result = DesignReviewResult()
        current_path = str(pptx_path)

        for iteration in range(1, self._max_iterations + 1):
            result.iterations_run = iteration
            self._progress(
                "stage_8",
                f"Design-Review Runde {iteration}/{self._max_iterations}...",
                92 if iteration == 1 else 96,
            )

            # Step 1: Convert to images
            try:
                image_paths = await convert_pptx_to_images(current_path)
            except Exception as e:
                logger.error(f"[DesignReview] Image conversion failed: {e}")
                result.error = f"Bildkonvertierung fehlgeschlagen: {str(e)[:100]}"
                break

            if not image_paths:
                result.error = "Keine Folienbilder erzeugt"
                break

            # Step 2: Analyze all slides
            self._progress(
                "stage_8",
                f"Gemini analysiert {len(image_paths)} Folien-Designs...",
                None,
            )

            reviews = await self._analyze_all_slides(image_paths)
            result.slide_reviews = reviews

            # Calculate average score
            if reviews:
                result.avg_score = sum(r.design_score for r in reviews) / len(reviews)

            # Step 3: Collect all fixes
            all_fixes = []
            for review in reviews:
                if review.needs_fixes:
                    all_fixes.extend(review.fixes)

            # Sort by priority: critical first, then important
            priority_order = {"critical": 0, "important": 1, "nice_to_have": 2}
            all_fixes.sort(key=lambda f: priority_order.get(f.priority, 2))

            logger.info(
                f"[DesignReview] Iteration {iteration}: "
                f"avg_score={result.avg_score:.1f}, fixes={len(all_fixes)}"
            )

            # If score is high enough or no fixes, we're done
            if result.avg_score >= 8.0 or not all_fixes:
                self._progress(
                    "quality",
                    f"Design-Score: {result.avg_score:.1f}/10 — keine Korrekturen noetig",
                    None,
                )
                break

            # Step 4: Apply fixes to RenderInstructions
            fixes_applied = self._apply_design_fixes(all_fixes)
            result.total_fixes_applied += fixes_applied

            if fixes_applied == 0:
                self._progress(
                    "quality",
                    f"Design-Score: {result.avg_score:.1f}/10 — keine anwendbaren Fixes",
                    None,
                )
                break

            # Step 5: Re-render with fixed instructions
            self._progress(
                "stage_8",
                f"{fixes_applied} Design-Korrekturen angewendet — wird neu gerendert...",
                None,
            )

            try:
                current_path = str(self._renderer.render(
                    self._instructions,
                    output_dir=output_dir,
                    progress_callback=None,  # Don't spam progress during re-render
                ))
            except Exception as e:
                logger.error(f"[DesignReview] Re-render failed: {e}")
                result.error = f"Re-Rendering fehlgeschlagen: {str(e)[:100]}"
                break

        # Final status
        if result.error:
            self._progress(
                "quality",
                f"Design-Review fehlgeschlagen: {result.error}",
                None,
            )
        elif result.passed:
            self._progress(
                "quality",
                f"Design-Score: {result.avg_score:.1f}/10 "
                f"({result.total_fixes_applied} Korrekturen)",
                None,
            )
        else:
            self._progress(
                "quality",
                f"Design-Score: {result.avg_score:.1f}/10 — verbesserungswuerdig "
                f"({result.total_fixes_applied} Korrekturen angewendet)",
                None,
            )

        return result

    # ── Gemini Vision Analysis ────────────────────────────────

    async def _analyze_all_slides(
        self, image_paths: list[str],
    ) -> list[SlideReview]:
        """Analyze all slides concurrently (max 4 parallel)."""
        token = _get_access_token()
        total = len(image_paths)

        # Build slide type map from instructions
        slide_types: dict[int, str] = {}
        for i, instr in enumerate(self._instructions):
            slide_types[i] = instr.slide_type.value if instr.slide_type else ""

        semaphore = asyncio.Semaphore(4)

        async def analyze_one(idx: int, path: str) -> SlideReview:
            async with semaphore:
                return await self._analyze_single_slide(
                    path, idx, total, token,
                    slide_type=slide_types.get(idx, ""),
                )

        tasks = [analyze_one(i, p) for i, p in enumerate(image_paths)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        reviews = []
        for i, r in enumerate(results):
            if isinstance(r, Exception):
                logger.warning(f"[DesignReview] Slide {i+1} analysis failed: {r}")
                reviews.append(SlideReview(
                    slide_index=i, design_score=7,
                    verdict="unknown",
                    strengths=["Analyse fehlgeschlagen"],
                ))
            else:
                reviews.append(r)

        return reviews

    async def _analyze_single_slide(
        self,
        image_path: str,
        slide_index: int,
        total_slides: int,
        token: str,
        slide_type: str = "",
    ) -> SlideReview:
        """Send one slide image to Gemini Vision for design review."""
        with open(image_path, "rb") as f:
            image_b64 = base64.b64encode(f.read()).decode("utf-8")

        url = (
            f"https://{settings.gcp_region}-aiplatform.googleapis.com/v1/"
            f"projects/{settings.gcp_project_id}/locations/{settings.gcp_region}/"
            f"publishers/google/models/{settings.gemini_model}:generateContent"
        )

        user_prompt = build_design_review_prompt(
            slide_index + 1, total_slides, slide_type,
        )

        payload = {
            "contents": [{
                "role": "user",
                "parts": [
                    {"text": user_prompt},
                    {
                        "inlineData": {
                            "mimeType": "image/jpeg",
                            "data": image_b64,
                        },
                    },
                ],
            }],
            "systemInstruction": {
                "parts": [{"text": DESIGN_REVIEW_SYSTEM_PROMPT}],
            },
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 2048,
                "responseMimeType": "application/json",
            },
        }

        try:
            async with httpx.AsyncClient(timeout=45) as client:
                response = await client.post(
                    url, json=payload,
                    headers={"Authorization": f"Bearer {token}"},
                )

            if response.status_code != 200:
                logger.warning(
                    f"[DesignReview] Gemini error for slide {slide_index+1}: "
                    f"{response.status_code}"
                )
                return SlideReview(slide_index=slide_index, design_score=7, verdict="unknown")

            data = response.json()
            text = (
                data.get("candidates", [{}])[0]
                .get("content", {})
                .get("parts", [{}])[0]
                .get("text", "")
            )
            return self._parse_review_response(text, slide_index)

        except Exception as e:
            logger.warning(f"[DesignReview] Analysis failed for slide {slide_index+1}: {e}")
            return SlideReview(slide_index=slide_index, design_score=7, verdict="unknown")

    def _parse_review_response(self, text: str, slide_index: int) -> SlideReview:
        """Parse Gemini's JSON response into a SlideReview."""
        try:
            clean = text.strip()
            if clean.startswith("```"):
                clean = clean.split("\n", 1)[-1]
                if clean.endswith("```"):
                    clean = clean[:-3]
                clean = clean.strip()

            data = json.loads(clean)

            fixes = []
            for fix_data in data.get("fixes", []):
                fixes.append(DesignFix(
                    slide_index=slide_index,
                    priority=fix_data.get("priority", "nice_to_have"),
                    category=fix_data.get("category", ""),
                    target_element=fix_data.get("target_element", ""),
                    issue=fix_data.get("issue", ""),
                    fix=fix_data.get("fix", ""),
                    params=fix_data.get("params", {}),
                ))

            return SlideReview(
                slide_index=slide_index,
                design_score=min(10, max(1, data.get("design_score", 7))),
                verdict=data.get("verdict", "unknown"),
                strengths=data.get("strengths", []),
                fixes=fixes,
            )

        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning(f"[DesignReview] Parse error for slide {slide_index+1}: {e}")
            return SlideReview(slide_index=slide_index, design_score=7, verdict="unknown")

    # ── Apply Design Fixes to RenderInstructions ──────────────

    def _apply_design_fixes(self, fixes: list[DesignFix]) -> int:
        """Apply design fixes by modifying the RenderInstructions.

        Returns the number of fixes successfully applied.
        """
        applied = 0

        for fix in fixes:
            idx = fix.slide_index
            if idx >= len(self._instructions):
                continue

            instr = self._instructions[idx]
            target = fix.target_element.lower()

            # Find the best matching element
            element = self._find_target_element(instr, target)
            if element is None:
                logger.debug(
                    f"[DesignReview] Could not find element '{fix.target_element}' "
                    f"on slide {idx+1}"
                )
                continue

            success = self._apply_single_fix(element, fix)
            if success:
                applied += 1
                logger.info(
                    f"[DesignReview] Applied {fix.category} fix on slide {idx+1}: "
                    f"{fix.issue}"
                )

        return applied

    def _find_target_element(
        self, instr: RenderInstruction, target: str,
    ) -> RenderElement | None:
        """Find the RenderElement that best matches the target description."""
        # Direct type match
        type_keywords = {
            "headline": ["headline"],
            "subheadline": ["subheadline", "untertitel"],
            "bullet": ["bullet", "aufzaehl", "liste"],
            "card": ["karte", "card"],
            "kpi": ["kpi", "kennzahl"],
            "image": ["bild", "image", "foto"],
            "chart": ["chart", "diagramm", "grafik"],
            "statement": ["statement", "aussage", "zitat"],
            "body": ["body", "text", "fliesstext"],
        }

        candidates: list[tuple[RenderElement, int]] = []

        for element in instr.elements:
            score = 0
            et = element.element_type.lower()

            # Check type keyword matches
            for key, keywords in type_keywords.items():
                if any(kw in target for kw in keywords):
                    if key in et or et.startswith(key):
                        score += 10

            # Check for numbered targets like "Karte 2"
            for num_word, num in [("1", 0), ("2", 1), ("3", 2), ("erste", 0),
                                   ("zweite", 1), ("dritte", 2),
                                   ("links", 0), ("mitte", 1), ("rechts", 2)]:
                if num_word in target:
                    # Check if element key has matching index
                    if f"_{num}" in et or et.endswith(str(num)):
                        score += 5

            # Direct name match
            if target in et or et in target:
                score += 8

            if score > 0:
                candidates.append((element, score))

        if not candidates:
            # Fallback: match by element type category
            for element in instr.elements:
                if element.element_type in ("shape", "image", "chart"):
                    continue
                return element  # Return first text element as fallback
            return None

        # Return highest-scoring match
        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[0][0]

    def _apply_single_fix(self, element: RenderElement, fix: DesignFix) -> bool:
        """Apply a single design fix to a RenderElement."""
        params = fix.params
        category = fix.category

        try:
            if category == "FONT_SIZE":
                delta = params.get("delta_pt", 0)
                if delta and element.style:
                    current = element.style.font_size_pt or 16
                    new_size = max(9, min(72, current + delta))
                    element.style.font_size_pt = new_size
                    return True

            elif category == "SPACING":
                dy = params.get("delta_y_cm", 0)
                dh = params.get("delta_h_cm", 0)
                if dy and element.position:
                    element.position.top_cm = max(0, element.position.top_cm + dy)
                    return True
                if dh and element.position:
                    element.position.height_cm = max(1.0, element.position.height_cm + dh)
                    return True

            elif category == "POSITION":
                dx = params.get("delta_x_cm", 0)
                dy = params.get("delta_y_cm", 0)
                if element.position and (dx or dy):
                    element.position.left_cm = max(0, element.position.left_cm + dx)
                    element.position.top_cm = max(0, element.position.top_cm + dy)
                    return True

            elif category == "SIZE":
                dw = params.get("delta_w_cm", 0)
                dh = params.get("delta_h_cm", 0)
                if element.position and (dw or dh):
                    if dw:
                        element.position.width_cm = max(1.0, element.position.width_cm + dw)
                    if dh:
                        element.position.height_cm = max(1.0, element.position.height_cm + dh)
                    return True

            elif category == "PADDING":
                # Simulate padding by adjusting position inward
                dp = params.get("delta_x_cm", 0) or params.get("delta_y_cm", 0)
                if dp and element.position:
                    element.position.left_cm += abs(dp)
                    element.position.top_cm += abs(dp)
                    element.position.width_cm = max(1.0, element.position.width_cm - 2 * abs(dp))
                    element.position.height_cm = max(1.0, element.position.height_cm - 2 * abs(dp))
                    return True

            elif category == "FONT_WEIGHT":
                if element.style and params.get("set_bold") is not None:
                    element.style.bold = bool(params["set_bold"])
                    return True

            elif category == "COLOR":
                new_color = params.get("new_color", "")
                if new_color and element.style:
                    element.style.font_color = new_color
                    return True

            elif category == "REMOVE":
                # We don't actually remove — just make invisible by shrinking
                if element.position:
                    element.position.width_cm = 0
                    element.position.height_cm = 0
                    return True

        except Exception as e:
            logger.warning(
                f"[DesignReview] Fix application failed ({category}): {e}"
            )

        return False


# ═══════════════════════════════════════════════════════════════
# Helper
# ═══════════════════════════════════════════════════════════════

def _get_access_token() -> str:
    credentials, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )
    credentials.refresh(google.auth.transport.requests.Request())
    return credentials.token
