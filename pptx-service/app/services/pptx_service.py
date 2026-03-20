"""PPTX generation service — maps structured slide data onto PowerPoint master layouts."""

from __future__ import annotations

import json
import logging
import tempfile
from pathlib import Path

from lxml import etree
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR, MSO_AUTO_SIZE
from pptx.enum.shapes import MSO_SHAPE_TYPE

from contextvars import ContextVar
from typing import Callable, Optional

from app.models.schemas import PresentationData, SlideContent
from app.services import template_service
from app.services.image_service import generate_image
from app.services.chart_service import generate_chart, parse_chart_data

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[str, str, Optional[int]], None]
_progress_ctx: ContextVar[Optional[ProgressCallback]] = ContextVar(
    "_progress_ctx", default=None
)

_LAYOUT_LABELS: dict[str, str] = {
    "title": "Titelfolie",
    "section": "Kapitelfolie",
    "content": "Inhalt",
    "two_column": "Zwei Spalten",
    "image": "Bildfolie",
    "chart": "Diagramm",
    "closing": "Abschlussfolie",
}


def _report_progress(step: str, message: str, progress: int | None = None) -> None:
    cb = _progress_ctx.get(None)
    if cb is not None:
        cb(step, message, progress)

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
    "chart": [
        ("diagramm", 90, []),
        ("chart", 90, []),
        ("grafik", 70, ["hintergrund"]),
        ("bild + inhalt", 40, []),
        ("bild", 30, ["titelfolie"]),
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
    "chart": 5,
    "closing": 0,
}


def generate_pptx(
    data: PresentationData,
    template_id: str = "default",
    progress_callback: ProgressCallback | None = None,
) -> Path:
    """Generate a PPTX file from structured presentation data."""
    token = _progress_ctx.set(progress_callback)
    try:
        _report_progress("template", "Template wird geladen...", 5)
        prs = template_service.load_presentation(template_id)

        analysis_map = _load_analysis_map(template_id)
        _remove_all_slides(prs)
        _set_metadata(prs, data)
        _report_progress("template", "Template bereit", 10)

        total = len(data.slides)
        for i, slide_data in enumerate(data.slides):
            progress = 10 + int((i / total) * 80)
            label = _LAYOUT_LABELS.get(slide_data.layout, slide_data.layout)
            title_preview = f" — {slide_data.title[:40]}" if slide_data.title else ""
            _report_progress(
                "slide", f"Folie {i + 1}/{total}: {label}{title_preview}", progress,
            )
            _add_slide(prs, slide_data, analysis_map)
            # Mark slide as done
            _report_progress(
                "slide", f"Folie {i + 1}/{total} fertig", 10 + int(((i + 1) / total) * 80),
            )

        _report_progress("saving", "Präsentation wird gespeichert...", 95)
        output_dir = Path(tempfile.mkdtemp(prefix="slidegen_"))
        safe_title = "".join(
            c if c.isalnum() or c in " _-" else "_" for c in data.title
        )[:50]
        output_path = output_dir / f"{safe_title}.pptx"
        prs.save(str(output_path))

        logger.info(f"Generated PPTX: {output_path} ({len(data.slides)} slides)")
        return output_path
    finally:
        _progress_ctx.reset(token)


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
        if data.subtitle and body_phs:
            body_phs[0].text = data.subtitle
    elif body_phs:
        # No TITLE placeholder (e.g. REWE template): use first BODY for title, second for subtitle
        body_phs[0].text = data.title
        if data.subtitle and len(body_phs) > 1:
            body_phs[1].text = data.subtitle

    # Fill picture placeholder if the title layout has one (e.g. "Titelfolie + Bild")
    picture_ph = _find_ph_by_type(slide, _PH_PICTURE)
    if picture_ph:
        desc = data.image_description or data.subtitle or data.title
        if desc:
            _report_progress("image", f"Titelbild wird generiert: {desc[:60]}")
            ph_width = picture_ph.width
            ph_height = picture_ph.height
            width_px = max(512, min(1536, int(ph_width / 914400 * 96)))
            height_px = max(512, min(1536, int(ph_height / 914400 * 96)))
            image_path = generate_image(desc, width=width_px, height=height_px)
            if image_path:
                try:
                    picture_ph.insert_picture(str(image_path))
                    logger.info(f"Inserted title image: {desc[:60]}...")
                except Exception:
                    logger.exception("Failed to insert title image")


def _handle_section(slide, data: SlideContent) -> None:
    """Populate a section header slide, optionally with content bullets."""
    title_ph = _find_ph_by_type(slide, _PH_TITLE)
    body_phs = _find_all_ph_by_types(slide, [_PH_BODY, _PH_SUBTITLE])
    content_ph = _find_content_placeholder(slide)

    if title_ph:
        title_ph.text = data.title
        if data.subtitle and body_phs:
            body_phs[0].text = data.subtitle
    elif body_phs:
        body_phs[0].text = data.title
        if data.subtitle and len(body_phs) > 1:
            body_phs[1].text = data.subtitle

    # Fill OBJECT placeholder with bullets if available (e.g. "Kapitelbeginn + Inhalt")
    if content_ph and data.bullets:
        _fill_bullet_list(content_ph, data.bullets)


def _handle_content(slide, data: SlideContent) -> None:
    """Populate a content slide with title and bullets."""
    title_ph = _find_ph_by_type(slide, _PH_TITLE)
    content_ph = _find_content_placeholder(slide)

    if title_ph:
        title_ph.text = _truncate_title(data.title)
    else:
        # Fallback: use a BODY placeholder for the title
        body_phs = _find_all_ph_by_types(slide, [_PH_BODY])
        if body_phs:
            body_phs[0].text = _truncate_title(data.title)

    if content_ph is None:
        return

    if data.bullets:
        _fill_bullet_list(content_ph, data.bullets)
    elif data.body:
        _set_text_with_bold(content_ph, data.body)


def _handle_two_column(slide, data: SlideContent) -> None:
    """Populate a two-column slide."""
    title_ph = _find_ph_by_type(slide, _PH_TITLE)
    if title_ph:
        title_ph.text = _truncate_title(data.title)

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
    """Populate an image slide: generate image and insert into picture placeholder.

    Also fills the OBJECT/content placeholder with bullets when the layout
    offers one (e.g. "Bild + Inhalt").
    """
    title_ph = _find_ph_by_type(slide, _PH_TITLE)
    if title_ph:
        title_ph.text = _truncate_title(data.title)

    picture_ph = _find_ph_by_type(slide, _PH_PICTURE)
    desc = data.image_description or data.body or ""

    image_inserted = False
    if picture_ph and desc:
        _report_progress("image", f"Bild wird generiert: {desc[:60]}")
        ph_width = picture_ph.width
        ph_height = picture_ph.height
        width_px = max(512, min(1536, int(ph_width / 914400 * 96)))
        height_px = max(512, min(1536, int(ph_height / 914400 * 96)))

        image_path = generate_image(desc, width=width_px, height=height_px)
        if image_path:
            try:
                picture_ph.insert_picture(str(image_path))
                logger.info(f"Inserted generated image into picture placeholder: {desc[:60]}...")
                image_inserted = True
            except Exception:
                logger.exception("Failed to insert image into picture placeholder")

    # Fill the content placeholder with bullets/body text (for "Bild + Inhalt" layouts)
    # Design-Prinzip "Klarheit vor Dekoration": Jedes Element muss einen Zweck haben.
    content_ph = _find_content_placeholder(slide)
    if content_ph:
        if data.bullets:
            _fill_bullet_list(content_ph, data.bullets)
        elif data.body:
            _set_text_with_bold(content_ph, data.body)
        elif desc:
            logger.warning("Image slide '%s' has no bullets — using description as fallback", data.title)
            _set_text_with_bold(content_ph, desc)


def _handle_closing(slide, data: SlideContent) -> None:
    """Populate a closing slide with title, subtitle, and optional bullets/body."""
    title_ph = _find_ph_by_type(slide, _PH_TITLE)
    content_ph = _find_content_placeholder(slide)
    body_phs = _find_all_ph_by_types(slide, [_PH_BODY, _PH_SUBTITLE])

    if title_ph:
        title_ph.text = _truncate_title(data.title)
        if data.subtitle and body_phs:
            body_phs[0].text = data.subtitle
    elif body_phs:
        body_phs[0].text = data.title
        if data.subtitle and len(body_phs) > 1:
            body_phs[1].text = data.subtitle

    # Fill content/OBJECT placeholder with bullets or body text
    if content_ph:
        if data.bullets:
            _fill_bullet_list(content_ph, data.bullets)
        elif data.body:
            _set_text_with_bold(content_ph, data.body)


def _handle_chart(slide, data: SlideContent) -> None:
    """Populate a chart slide: generate chart image and insert into picture placeholder."""
    title_ph = _find_ph_by_type(slide, _PH_TITLE)
    if title_ph:
        title_ph.text = _truncate_title(data.title)

    # Parse chart JSON from the slide data
    chart_data = None
    if data.chart_data:
        import json
        try:
            chart_data = json.loads(data.chart_data)
        except (json.JSONDecodeError, ValueError):
            logger.warning(f"Failed to parse chart JSON: {data.chart_data[:100]}")

    if not chart_data:
        # Fallback: try to extract from body text
        chart_data = parse_chart_data(data.body) if data.body else None

    if not chart_data:
        # No chart data — fall back to content handler
        logger.warning("No chart data found, falling back to content handler")
        _handle_content(slide, data)
        return

    # Load template profile for chart styling
    chart_colors = _load_chart_colors()

    # Find picture or chart placeholder for the chart image
    picture_ph = _find_ph_by_type(slide, _PH_PICTURE)
    if not picture_ph:
        # Fall back to any OBJECT placeholder
        picture_ph = _find_content_placeholder(slide)

    if picture_ph:
        _report_progress("chart", f"Diagramm wird erstellt: {chart_data.get('type', 'chart')}")
        ph_width = picture_ph.width
        ph_height = picture_ph.height
        width_px = max(600, min(1800, int(ph_width / 914400 * 96)))
        height_px = max(400, min(1200, int(ph_height / 914400 * 96)))

        chart_path = generate_chart(
            chart_data=chart_data,
            colors=chart_colors if chart_colors else None,
            width_px=width_px,
            height_px=height_px,
        )

        if chart_path:
            try:
                if hasattr(picture_ph, 'insert_picture'):
                    picture_ph.insert_picture(str(chart_path))
                else:
                    # OBJECT placeholder: add picture as a shape
                    from pptx.util import Emu
                    slide.shapes.add_picture(
                        str(chart_path),
                        picture_ph.left, picture_ph.top,
                        picture_ph.width, picture_ph.height,
                    )
                logger.info(f"Inserted chart image: {chart_data.get('type', 'unknown')} chart")
                return
            except Exception:
                logger.exception("Failed to insert chart image")

    # Last resort: put chart title/data description in text
    content_ph = _find_content_placeholder(slide)
    if content_ph:
        content_ph.text = f"[Diagramm: {chart_data.get('title', data.title)}]"


def _load_chart_colors() -> list[str] | None:
    """Try to load chart colors from the template profile."""
    # Check for profile JSON in the templates directory
    import json
    from app.config import settings

    templates_dir = settings.templates_dir
    for profile_path in templates_dir.glob("*.profile.json"):
        try:
            with open(profile_path, "r", encoding="utf-8") as f:
                profile = json.load(f)
            colors = profile.get("color_dna", {}).get("chart_colors", [])
            if colors:
                return colors
        except Exception:
            pass
    return None


_LAYOUT_HANDLERS = {
    "title": _handle_title,
    "section": _handle_section,
    "content": _handle_content,
    "two_column": _handle_two_column,
    "image": _handle_image,
    "chart": _handle_chart,
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


import re as _re

# Regex to split text on **bold** markers
_BOLD_RE = _re.compile(r'\*\*(.+?)\*\*')


def _fill_bullets(placeholder, markdown_text: str) -> None:
    """Fill a placeholder with bullet lines parsed from Markdown."""
    lines = [
        line.lstrip("- ").lstrip("* ").strip()
        for line in markdown_text.strip().split("\n")
        if line.strip()
    ]
    _fill_bullet_list(placeholder, lines)


_NS_A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
_NS_P = "{http://schemas.openxmlformats.org/presentationml/2006/main}"

# Default bullet character used when the template has buNone at level 0
_DEFAULT_BULLET_CHAR = "\u2022"  # •
_DEFAULT_BULLET_FONT = "Arial"


def _needs_bullet_char(tf) -> bool:
    """Check if the text frame's level-0 paragraphs lack a bullet character.

    Inspects the lstStyle for buNone or missing buChar at level 0/1.
    When the master defines buNone, bullets render as plain text — we fix that.
    """
    txBody = tf._txBody
    lstStyle = txBody.find(f"{_NS_A}lstStyle")
    if lstStyle is not None and len(lstStyle) > 0:
        lvl1 = lstStyle.find(f"{_NS_A}lvl1pPr")
        if lvl1 is not None:
            if lvl1.find(f"{_NS_A}buNone") is not None:
                return True
            if lvl1.find(f"{_NS_A}buChar") is not None:
                return False
    # Fall back: check if placeholder inherits from layout/master with buNone
    # If no bullet info at all, default to adding bullets for OBJECT placeholders
    return True


def _ensure_bullet_char(paragraph) -> None:
    """Add an explicit bullet character to a paragraph's XML properties."""
    pPr = paragraph._p.find(f"{_NS_A}pPr")
    if pPr is None:
        pPr = etree.SubElement(paragraph._p, f"{_NS_A}pPr")
        paragraph._p.insert(0, pPr)

    # Remove buNone if present
    buNone = pPr.find(f"{_NS_A}buNone")
    if buNone is not None:
        pPr.remove(buNone)

    # Add buFont + buChar if not already there
    if pPr.find(f"{_NS_A}buChar") is None:
        buFont = etree.SubElement(pPr, f"{_NS_A}buFont")
        buFont.set("typeface", _DEFAULT_BULLET_FONT)
        buChar = etree.SubElement(pPr, f"{_NS_A}buChar")
        buChar.set("char", _DEFAULT_BULLET_CHAR)


def _truncate_title(text: str, max_chars: int = 50) -> str:
    """Truncate a title to fit within the maximum character limit."""
    if len(text) <= max_chars:
        return text
    # Try to cut at a word boundary
    truncated = text[:max_chars]
    last_space = truncated.rfind(" ")
    if last_space > max_chars * 0.6:
        truncated = truncated[:last_space]
    return truncated.rstrip(" ,:;-")


def _safe_clear_text_frame(tf):
    """Clear text frame content while preserving the template's lstStyle element.

    python-pptx's tf.clear() removes the lstStyle which contains font sizes,
    bullet symbols and indentation inherited from the slide layout / master.
    """
    from copy import deepcopy

    txBody = tf._txBody
    lstStyle = txBody.find(f"{_NS_A}lstStyle")
    lstStyle_copy = deepcopy(lstStyle) if lstStyle is not None and len(lstStyle) > 0 else None

    tf.clear()
    tf.word_wrap = True

    if lstStyle_copy is not None:
        new_lstStyle = txBody.find(f"{_NS_A}lstStyle")
        if new_lstStyle is not None:
            txBody.replace(new_lstStyle, lstStyle_copy)
        else:
            first_p = txBody.find(f"{_NS_A}p")
            if first_p is not None:
                txBody.insert(list(txBody).index(first_p), lstStyle_copy)


def _fill_bullet_list(placeholder, items: list[str]) -> None:
    """Fill a placeholder with a list of bullet strings, rendering **bold** as actual bold.

    Preserves the template's lstStyle to maintain font sizes, bullet symbols and indentation.
    Adds explicit bullet characters when the template doesn't provide them at level 0.
    """
    tf = placeholder.text_frame
    _safe_clear_text_frame(tf)

    # Detect whether level 0 has a bullet character from the master/layout.
    # If buNone is set or no buChar exists, we add an explicit bullet.
    needs_explicit_bullet = _needs_bullet_char(tf)

    for i, item in enumerate(items):
        if i == 0:
            p = tf.paragraphs[0]
        else:
            p = tf.add_paragraph()
        p.level = 0
        if needs_explicit_bullet:
            _ensure_bullet_char(p)
        _set_paragraph_with_bold(p, item)


def _set_paragraph_with_bold(paragraph, text: str) -> None:
    """Parse markdown bold (**text**) and create proper bold/normal runs."""
    # Split text on **bold** markers
    parts = _BOLD_RE.split(text)
    # parts alternates: [normal, bold, normal, bold, ...]
    # Even indices are normal text, odd indices are bold text
    if len(parts) == 1 and '**' not in text:
        # No bold formatting — simple text
        paragraph.text = text
        return

    # Clear any existing runs, then add formatted runs
    paragraph.clear()
    for idx, part in enumerate(parts):
        if not part:
            continue
        run = paragraph.add_run()
        run.text = part
        if idx % 2 == 1:
            # Odd index = was inside **bold** markers
            run.font.bold = True


def _set_text_with_bold(placeholder, text: str) -> None:
    """Set placeholder text, rendering any **bold** markdown as actual bold.
    
    Preserves the template's lstStyle to maintain font sizes.
    """
    tf = placeholder.text_frame
    _safe_clear_text_frame(tf)
    _set_paragraph_with_bold(tf.paragraphs[0], text)
