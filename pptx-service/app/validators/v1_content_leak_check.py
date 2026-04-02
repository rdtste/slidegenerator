"""Content leak detection for V1 SlideContent model.

Mirrors the L001-L003 logic from content_leak_rules.py but operates on
the V1 SlideContent model (used by pptx_service.py / template-based generation).

This ensures both V1 (template) and V2 (design) pipelines have identical
content leak detection quality.
"""

from __future__ import annotations

import logging
import re

from app.models.schemas import SlideContent, PresentationData

logger = logging.getLogger(__name__)

# Same patterns as content_leak_rules.py — single source of truth
_DESCRIPTOR_PATTERNS: list[re.Pattern] = [
    re.compile(r'\b\w+\s+icon\b', re.IGNORECASE),
    re.compile(r'\bicon\s+of\b', re.IGNORECASE),
    re.compile(r'\bicon:\s', re.IGNORECASE),
    re.compile(r'\b(Symbol|Piktogramm|Grafik)\s+(von|fuer|eines|einer)\b', re.IGNORECASE),
    re.compile(r'\b(stock\s+photo|stock\s+image|stock\s+bild)\b', re.IGNORECASE),
    re.compile(r'\b(photorealistic|hyperrealistic|4k|8k|high.?resolution)\b', re.IGNORECASE),
    re.compile(r'\b(illustration\s+of|photo\s+of|image\s+of|picture\s+of)\b', re.IGNORECASE),
    re.compile(r'\b(Bild\s+von|Foto\s+von|Darstellung\s+von)\b', re.IGNORECASE),
    re.compile(r'\[.*?\]'),
    re.compile(r'\{.*?\}'),
    re.compile(r'lorem\s+ipsum', re.IGNORECASE),
    re.compile(r'\bXYZ\b'),
    re.compile(r'\bTBD\b'),
    re.compile(r'\bTODO\b', re.IGNORECASE),
    re.compile(r'\bPLACEHOLDER\b', re.IGNORECASE),
]

_LEAKED_ICON_HINTS: set[str] = {
    "monastery icon", "shield icon", "scroll icon", "book icon",
    "gear icon", "people icon", "chart icon", "globe icon",
    "shield or scroll icon", "buch mit feder", "landkarte mit pin",
    "hopfenpflanze", "zahnrad", "menschen", "diagramm",
}


def _is_leaked_text(text: str) -> str | None:
    """Check if text contains a descriptor leak. Returns description or None."""
    if not text or len(text) < 3:
        return None

    text_lower = text.lower().strip()

    if text_lower in _LEAKED_ICON_HINTS:
        return f"raw icon descriptor '{text}'"

    for pattern in _DESCRIPTOR_PATTERNS:
        match = pattern.search(text)
        if match:
            return f"descriptor pattern '{match.group()}' in '{text[:60]}'"

    return None


def sanitize_slide_content(slide: SlideContent, slide_index: int) -> SlideContent:
    """Scan and sanitize a V1 SlideContent for descriptor leaks.

    Clears any field that contains leaked internal metadata.
    Returns the same (mutated) SlideContent object.
    """
    # Check title
    leak = _is_leaked_text(slide.title)
    if leak:
        logger.warning(f"[V1 Leak Check] Slide {slide_index + 1} title: {leak} — cleared")
        slide.title = ""

    # Check subtitle
    leak = _is_leaked_text(slide.subtitle)
    if leak:
        logger.warning(f"[V1 Leak Check] Slide {slide_index + 1} subtitle: {leak} — cleared")
        slide.subtitle = ""

    # Check body
    leak = _is_leaked_text(slide.body)
    if leak:
        logger.warning(f"[V1 Leak Check] Slide {slide_index + 1} body: {leak} — cleared")
        slide.body = ""

    # Check bullets
    cleaned_bullets = []
    for i, bullet in enumerate(slide.bullets):
        leak = _is_leaked_text(bullet)
        if leak:
            logger.warning(f"[V1 Leak Check] Slide {slide_index + 1} bullet[{i}]: {leak} — removed")
        else:
            cleaned_bullets.append(bullet)
    slide.bullets = cleaned_bullets

    # Check left/right columns
    leak = _is_leaked_text(slide.left_column)
    if leak:
        logger.warning(f"[V1 Leak Check] Slide {slide_index + 1} left_column: {leak} — cleared")
        slide.left_column = ""

    leak = _is_leaked_text(slide.right_column)
    if leak:
        logger.warning(f"[V1 Leak Check] Slide {slide_index + 1} right_column: {leak} — cleared")
        slide.right_column = ""

    # Ensure image_description doesn't leak into visible text fields
    if slide.image_description and len(slide.image_description) >= 10:
        img_desc_lower = slide.image_description.lower()
        for field_name in ("title", "subtitle", "body"):
            field_val = getattr(slide, field_name, "")
            if field_val and img_desc_lower in field_val.lower():
                logger.warning(
                    f"[V1 Leak Check] Slide {slide_index + 1} {field_name} "
                    f"contains image_description — cleared"
                )
                setattr(slide, field_name, "")

    return slide


def sanitize_presentation(data: PresentationData) -> PresentationData:
    """Scan and sanitize all slides in a V1 PresentationData for descriptor leaks."""
    for i, slide in enumerate(data.slides):
        sanitize_slide_content(slide, i)
    return data
