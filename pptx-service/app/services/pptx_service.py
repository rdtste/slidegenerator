"""PPTX generation service — maps structured slide data onto PowerPoint master layouts."""

from __future__ import annotations

import json
import logging
import tempfile
from pathlib import Path

from lxml import etree
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE_TYPE

from app.models.schemas import PresentationData, SlideContent
from app.services import template_service

logger = logging.getLogger(__name__)

# Placeholder type constants from the OOXML spec
_PH_TITLE = 1       # TITLE
_PH_BODY = 2        # BODY
_PH_SUBTITLE = 3    # SUBTITLE (rare in custom templates)
_PH_OBJECT = 7      # OBJECT (generic content)
_PH_PICTURE = 18    # PICTURE

# Scored keyword patterns per layout type.
# Each entry: (substring_to_match, score, negative_substrings_that_disqualify)
_LAYOUT_SCORES: dict[str, list[tuple[str, int, list[str]]]] = {
    "title": [
        ("titelfolie", 80, ["bild", "farbig", "foto"]),
        ("titelfolie", 50, ["farbig"]),
        ("title slide", 70, []),
        ("titel", 30, ["nur", "farbig", "kapitelbeginn"]),
    ],
    "section": [
        ("kapitelbeginn", 90, ["inhalt"]),
        ("kapitelbeginn", 60, []),
        ("abschnitt", 70, []),
        ("section", 70, []),
        ("zwischentitel", 60, []),
    ],
    "content": [
        ("inhalt 1-spaltig", 100, []),
        ("inhalt 1", 90, []),
        ("content", 70, ["picture", "contact"]),
        ("inhalt", 50, ["spaltig", "bild", "kapitel"]),
        ("aufz\u00e4hlung", 60, []),
        ("bullet", 60, []),
        ("text", 30, ["nur"]),
    ],
    "two_column": [
        ("inhalt 2-spaltig", 100, []),
        ("2-spaltig", 90, []),
        ("two column", 80, []),
        ("vergleich", 70, []),
        ("comparison", 70, []),
    ],
    "image": [
        ("bild + inhalt", 90, []),
        ("bild + box", 80, []),
        ("bild + inhalt (1:2)", 85, []),
        ("bild", 60, ["titelfolie"]),
        ("image", 60, []),
        ("picture", 50, []),
        ("foto", 50, []),
    ],
    "closing": [
        ("danke", 100, []),
        ("thank", 100, []),
        ("abschluss", 90, []),
        ("ende", 80, []),
        ("closing", 80, []),
        ("kontakt", 40, ["team", "bild"]),
        ("titelfolie", 20, ["bild", "farbig", "foto"]),
    ],
}

# Fallback layout indices for standard PowerPoint templates (no custom template)
_FALLBACK_LAYOUT: dict[str, int] = {
    "title": 0,
    "section": 2,
    "content": 1,
    "two_column": 3,
    "image": 5,
    "closing": 0,
}


def generate_pptx(data: PresentationData, template_id: str = "default") -> Path:
    """Generate a PPTX file from structured presentation data."""
    prs = template_service.load_presentation(template_id)

    # Load AI analysis mapping if available
    analysis_map = _load_analysis_map(template_id)

    # Remove all existing demo/example slides from the template
    _remove_all_slides(prs)

    _set_metadata(prs, data)

    for slide_data in data.slides:
        _add_slide(prs, slide_data, analysis_map)

    output_dir = Path(tempfile.mkdtemp(prefix="k8marp_"))
    safe_title = "".join(c if c.isalnum() or c in " _-" else "_" for c in data.title)[:50]
    output_path = output_dir / f"{safe_title}.pptx"
    prs.save(str(output_path))

    logger.info(f"Generated PPTX: {output_path} ({len(data.slides)} slides)")
    return output_path


def _remove_all_slides(prs: Presentation) -> None:
    """Remove all existing slides from a presentation, keeping only layouts/masters."""
    slide_count = len(prs.slides)
    if slide_count == 0:
        return

    sldIdLst = prs.slides._sldIdLst
    ns = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"

    for _ in range(slide_count):
        sldId = sldIdLst[0]
        rId = sldId.get(f"{ns}id") or sldId.get("r:id")
        if rId:
            prs.part.drop_rel(rId)
        sldIdLst.remove(sldId)

    logger.info(f"Removed {slide_count} existing template slides")


def _set_metadata(prs: Presentation, data: PresentationData) -> None:
    """Set presentation metadata."""
    prs.core_properties.title = data.title
    if data.author:
        prs.core_properties.author = data.author


def _add_slide(prs: Presentation, slide_data: SlideContent, analysis_map: dict[str, int] | None = None) -> None:
    """Add a single slide to the presentation based on its layout type."""
    layout_idx = _resolve_layout(prs, slide_data.layout, analysis_map)
    layout = prs.slide_layouts[layout_idx]
    slide = prs.slides.add_slide(layout)

    logger.debug(
        f"Added slide: layout={slide_data.layout} -> "
        f"idx={layout_idx} ({layout.name}), "
        f"placeholders={[ph.placeholder_format.idx for ph in slide.placeholders]}"
    )

    if slide_data.notes:
        slide.notes_slide.notes_text_frame.text = slide_data.notes

    handler = _LAYOUT_HANDLERS.get(slide_data.layout, _handle_content)
    handler(slide, slide_data)


def _load_analysis_map(template_id: str) -> dict[str, int] | None:
    """Load AI-generated layout type → index mapping from analysis JSON."""
    template_path = template_service.get_template_path(template_id)
    if not template_path:
        return None

    analysis_path = template_path.parent / f"{template_id}.analysis.json"
    if not analysis_path.is_file():
        return None

    try:
        with open(analysis_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        mappings = data.get("layout_mappings", [])
        result: dict[str, int] = {}
        for m in mappings:
            mapped_type = m.get("mapped_type", "")
            idx = m.get("layout_index")
            if mapped_type and mapped_type != "unused" and isinstance(idx, int):
                # First mapping per type wins (AI returns best-match first)
                if mapped_type not in result:
                    result[mapped_type] = idx
        if result:
            logger.info(f"Loaded AI analysis map for '{template_id}': {result}")
        return result if result else None
    except Exception:
        logger.warning(f"Failed to load analysis for '{template_id}', using keyword fallback")
        return None


def _resolve_layout(prs: Presentation, layout_type: str, analysis_map: dict[str, int] | None = None) -> int:
    """Resolve layout type to a template slide layout index.

    Uses AI analysis mapping when available, falls back to scored keyword matching.
    """
    # 1. Try AI analysis mapping
    if analysis_map and layout_type in analysis_map:
        idx = analysis_map[layout_type]
        if 0 <= idx < len(prs.slide_layouts):
            logger.info(
                f"Layout '{layout_type}' -> [{idx}] "
                f'"{prs.slide_layouts[idx].name}" (AI analysis)'
            )
            return idx

    # 2. Fall back to scored keyword matching
    score_rules = _LAYOUT_SCORES.get(layout_type)
    if not score_rules:
        fallback = _FALLBACK_LAYOUT.get(layout_type, 1)
        return min(fallback, len(prs.slide_layouts) - 1)

    best_idx = -1
    best_score = 0

    for idx, layout in enumerate(prs.slide_layouts):
        name_lower = layout.name.lower()
        for pattern, score, negatives in score_rules:
            if pattern in name_lower:
                if any(neg in name_lower for neg in negatives):
                    continue
                if score > best_score:
                    best_score = score
                    best_idx = idx
                break  # first matching pattern wins for this layout

    if best_idx >= 0:
        logger.info(
            f"Layout '{layout_type}' -> [{best_idx}] "
            f'"{prs.slide_layouts[best_idx].name}" (score={best_score})'
        )
        return best_idx

    fallback = _FALLBACK_LAYOUT.get(layout_type, 1)
    result = min(fallback, len(prs.slide_layouts) - 1)
    logger.warning(f"Layout '{layout_type}' -> fallback [{result}]")
    return result


# --- Layout handlers ---
# All handlers use _find_ph_by_type() to locate placeholders by their
# semantic type rather than by hardcoded index.

def _handle_title(slide, data: SlideContent) -> None:
    """Populate a title slide."""
    title_ph = _find_ph_by_type(slide, _PH_TITLE)
    body_phs = _find_all_ph_by_types(slide, [_PH_BODY, _PH_SUBTITLE, _PH_OBJECT])

    if title_ph:
        title_ph.text = data.title
        # Subtitle goes into the first body placeholder
        if data.subtitle and body_phs:
            body_phs[0].text = data.subtitle
    elif body_phs:
        # No TITLE placeholder (e.g. REWE template): use first BODY for title, second for subtitle
        body_phs[0].text = data.title
        if data.subtitle and len(body_phs) > 1:
            body_phs[1].text = data.subtitle


def _handle_section(slide, data: SlideContent) -> None:
    """Populate a section header slide."""
    title_ph = _find_ph_by_type(slide, _PH_TITLE)
    body_phs = _find_all_ph_by_types(slide, [_PH_BODY, _PH_SUBTITLE, _PH_OBJECT])

    if title_ph:
        title_ph.text = data.title
        if data.subtitle and body_phs:
            body_phs[0].text = data.subtitle
    elif body_phs:
        body_phs[0].text = data.title
        if data.subtitle and len(body_phs) > 1:
            body_phs[1].text = data.subtitle


def _handle_content(slide, data: SlideContent) -> None:
    """Populate a content slide with title and bullets."""
    title_ph = _find_ph_by_type(slide, _PH_TITLE)
    content_ph = _find_content_placeholder(slide)

    if title_ph:
        title_ph.text = data.title
    else:
        # Fallback: use a BODY placeholder for the title
        body_phs = _find_all_ph_by_types(slide, [_PH_BODY])
        if body_phs:
            body_phs[0].text = data.title

    if content_ph is None:
        return

    if data.bullets:
        _fill_bullet_list(content_ph, data.bullets)
    elif data.body:
        content_ph.text = data.body


def _handle_two_column(slide, data: SlideContent) -> None:
    """Populate a two-column slide."""
    title_ph = _find_ph_by_type(slide, _PH_TITLE)
    if title_ph:
        title_ph.text = data.title

    # Find the two OBJECT/BODY placeholders for columns
    col_phs = _find_all_ph_by_types(slide, [_PH_OBJECT])
    if len(col_phs) < 2:
        # Fallback to BODY types (skip the first if it's being used for title-like content)
        col_phs = _find_all_ph_by_types(slide, [_PH_OBJECT, _PH_BODY])
        if title_ph is None and len(col_phs) > 2:
            col_phs = col_phs[1:]  # skip the one used for title

    left_ph = col_phs[0] if len(col_phs) > 0 else None
    right_ph = col_phs[1] if len(col_phs) > 1 else None

    if left_ph and data.left_column:
        _fill_bullets(left_ph, data.left_column)
    elif left_ph and data.bullets:
        half = len(data.bullets) // 2 or 1
        _fill_bullet_list(left_ph, data.bullets[:half])

    if right_ph and data.right_column:
        _fill_bullets(right_ph, data.right_column)
    elif right_ph and data.bullets:
        half = len(data.bullets) // 2 or 1
        _fill_bullet_list(right_ph, data.bullets[half:])


def _handle_image(slide, data: SlideContent) -> None:
    """Populate an image slide (text description in content placeholder)."""
    title_ph = _find_ph_by_type(slide, _PH_TITLE)
    if title_ph:
        title_ph.text = data.title

    content_ph = _find_content_placeholder(slide)
    if content_ph:
        desc = data.image_description or data.body or "(Bild hier einf\u00fcgen)"
        content_ph.text = desc


def _handle_closing(slide, data: SlideContent) -> None:
    """Populate a closing slide."""
    title_ph = _find_ph_by_type(slide, _PH_TITLE)
    body_phs = _find_all_ph_by_types(slide, [_PH_BODY, _PH_SUBTITLE, _PH_OBJECT])

    if title_ph:
        title_ph.text = data.title
        if data.subtitle and body_phs:
            body_phs[0].text = data.subtitle
    elif body_phs:
        body_phs[0].text = data.title
        if data.subtitle and len(body_phs) > 1:
            body_phs[1].text = data.subtitle


_LAYOUT_HANDLERS = {
    "title": _handle_title,
    "section": _handle_section,
    "content": _handle_content,
    "two_column": _handle_two_column,
    "image": _handle_image,
    "closing": _handle_closing,
}


# --- Placeholder helpers ---

def _find_ph_by_type(slide, ph_type: int):
    """Find the first placeholder matching a given type constant."""
    for ph in slide.placeholders:
        if ph.placeholder_format.type == ph_type:
            return ph
    return None


def _find_all_ph_by_types(slide, ph_types: list[int]) -> list:
    """Find all placeholders matching any of the given types, ordered by idx.

    Excludes footer/date/slide-number placeholders (types 13, 15, 16).
    """
    _SKIP_TYPES = {13, 15, 16}  # SLIDE_NUMBER, FOOTER, DATE
    result = []
    for ph in slide.placeholders:
        t = ph.placeholder_format.type
        if t in _SKIP_TYPES:
            continue
        if t in ph_types:
            result.append(ph)
    result.sort(key=lambda p: p.placeholder_format.idx)
    return result


def _find_content_placeholder(slide):
    """Find the best placeholder for body/bullet content.

    Prefers OBJECT type, then BODY type. Skips the TITLE placeholder.
    """
    # First try OBJECT placeholders (most common for content in custom templates)
    for ph in slide.placeholders:
        if ph.placeholder_format.type == _PH_OBJECT:
            return ph

    # Then try BODY placeholders, skipping any that look like title/subtitle
    title_ph = _find_ph_by_type(slide, _PH_TITLE)
    for ph in slide.placeholders:
        t = ph.placeholder_format.type
        if t == _PH_BODY and ph != title_ph:
            # Skip date/footer/slide-number
            if ph.placeholder_format.idx >= 10:
                return ph

    # Last resort: any BODY placeholder
    for ph in slide.placeholders:
        if ph.placeholder_format.type == _PH_BODY:
            return ph

    return None


def _fill_bullets(placeholder, markdown_text: str) -> None:
    """Fill a placeholder with bullet lines parsed from Markdown."""
    lines = [
        line.lstrip("- ").lstrip("* ").strip()
        for line in markdown_text.strip().split("\n")
        if line.strip()
    ]
    _fill_bullet_list(placeholder, lines)


def _fill_bullet_list(placeholder, items: list[str]) -> None:
    """Fill a placeholder with a list of bullet strings."""
    tf = placeholder.text_frame
    tf.clear()
    for i, item in enumerate(items):
        if i == 0:
            tf.paragraphs[0].text = item
            tf.paragraphs[0].level = 0
        else:
            p = tf.add_paragraph()
            p.text = item
            p.level = 0
