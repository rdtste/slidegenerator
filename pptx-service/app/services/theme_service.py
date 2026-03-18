"""Theme extraction service — extracts visual properties from PowerPoint templates."""

from __future__ import annotations

import logging
import zipfile
from io import BytesIO
from pathlib import Path

from lxml import etree
from pydantic import BaseModel, Field

from app.services.template_service import get_template_path, load_presentation
from app.models.schemas import TemplateStructure, LayoutInfo, PlaceholderInfo

logger = logging.getLogger(__name__)

_NS = {"a": "http://schemas.openxmlformats.org/drawingml/2006/main"}

# Placeholder types we care about for constraints
_PH_TITLE = 1
_PH_BODY = 2
_PH_OBJECT = 7
_PH_PICTURE = 18
# Skip these meta-placeholders
_PH_SKIP = {13, 15, 16}  # SLIDE_NUMBER, FOOTER, DATE


class PlaceholderConstraint(BaseModel):
    """Dimensional constraints for a single placeholder."""
    role: str  # "title", "subtitle", "content", "picture"
    width_cm: float
    height_cm: float
    font_size_pt: float
    max_lines: int
    max_chars_per_line: int


class LayoutConstraint(BaseModel):
    """Design constraints for a specific slide layout."""
    layout_name: str
    layout_type: str  # our mapped type: title, section, content, two_column, image, closing
    placeholders: list[PlaceholderConstraint] = Field(default_factory=list)
    max_bullets: int = 0
    max_chars_per_bullet: int = 0
    title_max_chars: int = 0


class TemplateTheme(BaseModel):
    template_id: str
    template_name: str = ""
    heading_font: str = "Calibri"
    body_font: str = "Calibri"
    bg_color: str = "#FFFFFF"
    text_color: str = "#000000"
    accent_color: str = "#0969da"
    accent2_color: str = "#22c55e"
    heading_color: str = "#000000"
    layouts: list[str] = Field(default_factory=list)
    slide_width_cm: float = 33.9
    slide_height_cm: float = 19.1
    layout_constraints: list[LayoutConstraint] = Field(default_factory=list)


def extract_theme(template_id: str) -> TemplateTheme | None:
    """Extract visual theme properties from a template."""
    path = get_template_path(template_id)
    if not path:
        return None

    theme = TemplateTheme(template_id=template_id)

    try:
        _extract_from_zip(path, theme)
    except Exception:
        logger.exception(f"Failed to extract theme from ZIP: {path}")

    try:
        prs = load_presentation(template_id)
        theme.layouts = [layout.name for layout in prs.slide_layouts]
        theme.slide_width_cm = round(prs.slide_width / 914400 * 2.54, 1)
        theme.slide_height_cm = round(prs.slide_height / 914400 * 2.54, 1)
        _extract_bg_color(prs, theme)
        _extract_layout_constraints(prs, theme)
    except Exception:
        logger.exception(f"Failed to extract layouts/bg from: {template_id}")

    logger.info(
        f"Extracted theme from {template_id}: "
        f"fonts={theme.heading_font}/{theme.body_font}, "
        f"bg={theme.bg_color}, text={theme.text_color}, accent={theme.accent_color}, "
        f"constraints for {len(theme.layout_constraints)} layouts"
    )
    return theme


def extract_structure(template_id: str) -> TemplateStructure | None:
    """Extract raw layout structure from a template for AI analysis."""
    path = get_template_path(template_id)
    if not path:
        return None

    try:
        prs = load_presentation(template_id)
    except Exception:
        logger.exception(f"Failed to load template for structure: {template_id}")
        return None

    _PH_TYPE_NAMES = {
        0: "TITLE_OR_CENTER", 1: "TITLE", 2: "BODY", 3: "SUBTITLE",
        7: "OBJECT", 10: "TABLE", 12: "CHART", 13: "SLIDE_NUMBER",
        14: "DATE", 15: "FOOTER", 16: "DATE", 18: "PICTURE",
    }

    structure = TemplateStructure(
        template_id=template_id,
        slide_width_cm=round(prs.slide_width / 914400 * 2.54, 1),
        slide_height_cm=round(prs.slide_height / 914400 * 2.54, 1),
    )

    for idx, layout in enumerate(prs.slide_layouts):
        layout_info = LayoutInfo(index=idx, name=layout.name)

        for ph in layout.placeholders:
            ph_type = ph.placeholder_format.type
            ph_idx = ph.placeholder_format.idx

            font_sizes = _get_font_sizes_from_xml(ph._element)

            layout_info.placeholders.append(PlaceholderInfo(
                index=ph_idx,
                type_id=ph_type,
                type_name=_PH_TYPE_NAMES.get(ph_type, f"UNKNOWN_{ph_type}"),
                name=ph.name,
                width_cm=_emu_to_cm(ph.width) if ph.width else 0,
                height_cm=_emu_to_cm(ph.height) if ph.height else 0,
                left_cm=_emu_to_cm(ph.left) if ph.left else 0,
                top_cm=_emu_to_cm(ph.top) if ph.top else 0,
                font_sizes_pt=sorted(set(font_sizes)),
            ))

        structure.layouts.append(layout_info)

    logger.info(f"Extracted structure for {template_id}: {len(structure.layouts)} layouts")
    return structure


def _extract_from_zip(path: Path, theme: TemplateTheme) -> None:
    """Parse theme XML from the OOXML ZIP to extract colors and fonts."""
    with open(path, "rb") as f:
        data = f.read()

    zf = zipfile.ZipFile(BytesIO(data))
    theme_files = sorted(n for n in zf.namelist() if "theme/theme" in n.lower() and n.endswith(".xml"))
    if not theme_files:
        return

    theme_xml = zf.read(theme_files[0])
    root = etree.fromstring(theme_xml)

    clr_scheme = root.find(".//a:clrScheme", _NS)
    if clr_scheme is not None:
        theme.template_name = clr_scheme.get("name", "")
        colors = _parse_color_scheme(clr_scheme)
        theme.text_color = colors.get("dk1", theme.text_color)
        theme.bg_color = colors.get("lt1", theme.bg_color)
        theme.heading_color = colors.get("dk2", colors.get("dk1", theme.heading_color))
        theme.accent_color = colors.get("accent1", theme.accent_color)
        theme.accent2_color = colors.get("accent2", colors.get("lt2", theme.accent2_color))

    font_scheme = root.find(".//a:fontScheme", _NS)
    if font_scheme is not None:
        major = font_scheme.find(".//a:majorFont/a:latin", _NS)
        minor = font_scheme.find(".//a:minorFont/a:latin", _NS)
        if major is not None:
            theme.heading_font = major.get("typeface", theme.heading_font)
        if minor is not None:
            theme.body_font = minor.get("typeface", theme.body_font)


def _parse_color_scheme(clr_scheme) -> dict[str, str]:
    """Parse a clrScheme element into a dict of {name: #hex}."""
    colors: dict[str, str] = {}
    for child in clr_scheme:
        tag = child.tag.split("}")[-1]
        srgb = child.find("a:srgbClr", _NS)
        sys_clr = child.find("a:sysClr", _NS)
        if srgb is not None:
            colors[tag] = f"#{srgb.get('val', '000000')}"
        elif sys_clr is not None:
            colors[tag] = f"#{sys_clr.get('lastClr', sys_clr.get('val', '000000'))}"
    return colors


def _extract_bg_color(prs, theme: TemplateTheme) -> None:
    """Try to extract the background color from the first slide master."""
    try:
        master = prs.slide_masters[0]
        fill = master.background.fill
        if fill.type is not None:
            fg = fill.fore_color
            if fg and fg.rgb:
                theme.bg_color = f"#{fg.rgb}"
    except Exception:
        pass


# ── Layout type mapping (mirrors pptx_service._LAYOUT_SCORES logic) ─────────

_LAYOUT_TYPE_KEYWORDS: dict[str, list[tuple[str, int, list[str]]]] = {
    "title": [
        ("titelfolie", 80, ["bild", "farbig", "foto"]),
        ("title slide", 70, []),
        ("titel", 30, ["nur", "farbig", "kapitelbeginn"]),
    ],
    "section": [
        ("kapitelbeginn", 90, ["inhalt"]),
        ("abschnitt", 70, []),
        ("section", 70, []),
    ],
    "content": [
        ("inhalt 1-spaltig", 100, []),
        ("inhalt 1", 90, []),
        ("content", 70, ["picture", "contact"]),
        ("inhalt", 50, ["spaltig", "bild", "kapitel"]),
    ],
    "two_column": [
        ("inhalt 2-spaltig", 100, []),
        ("2-spaltig", 90, []),
        ("two column", 80, []),
        ("two_column", 80, []),
    ],
    "image": [
        ("bild + inhalt", 100, []),
        ("bild", 70, ["nur", "titel"]),
        ("image", 70, []),
        ("picture", 60, []),
    ],
    "closing": [
        ("kontakt", 90, []),
        ("closing", 80, []),
        ("end", 50, []),
    ],
}


def _classify_layout(layout_name: str) -> str | None:
    """Map a slide layout name to one of our layout types using scored matching."""
    name_lower = layout_name.lower()
    best_type: str | None = None
    best_score = 0

    for layout_type, patterns in _LAYOUT_TYPE_KEYWORDS.items():
        for substring, score, negatives in patterns:
            if substring in name_lower:
                if any(neg in name_lower for neg in negatives):
                    continue
                if score > best_score:
                    best_score = score
                    best_type = layout_type

    return best_type


def _get_font_sizes_from_xml(ph_element) -> list[float]:
    """Extract font sizes (pt) from placeholder XML (lstStyle / defRPr)."""
    sizes: list[float] = []
    for defRPr in ph_element.findall(".//{http://schemas.openxmlformats.org/drawingml/2006/main}defRPr"):
        sz = defRPr.get("sz")
        if sz:
            sizes.append(int(sz) / 100)
    for rPr in ph_element.findall(".//{http://schemas.openxmlformats.org/drawingml/2006/main}rPr"):
        sz = rPr.get("sz")
        if sz:
            sizes.append(int(sz) / 100)
    return sizes


def _emu_to_cm(emu: int) -> float:
    return round(emu / 914400 * 2.54, 1) if emu else 0.0


def _estimate_capacity(width_cm: float, height_cm: float, font_pt: float) -> tuple[int, int]:
    """Estimate max_lines and max_chars_per_line given area and font size."""
    line_height_cm = font_pt * 0.0353 * 1.5  # pt→cm × 1.5 spacing
    char_width_cm = font_pt * 0.0353 * 0.55  # approximate char width
    max_lines = int(height_cm / line_height_cm) if line_height_cm > 0 else 0
    max_chars = int(width_cm / char_width_cm) if char_width_cm > 0 else 0
    return max_lines, max_chars


def _ph_role(ph_type: int, layout_type: str, is_first_object: bool) -> str:
    """Determine the semantic role of a placeholder."""
    if ph_type == _PH_TITLE:
        return "title"
    if ph_type == _PH_PICTURE:
        return "picture"
    if ph_type == _PH_OBJECT:
        return "content"
    if ph_type == _PH_BODY:
        if layout_type == "title":
            return "subtitle"
        return "subtitle"
    return "other"


def _extract_layout_constraints(prs, theme: TemplateTheme) -> None:
    """Extract dimensional constraints for each mapped layout."""
    for layout in prs.slide_layouts:
        layout_type = _classify_layout(layout.name)
        if not layout_type:
            continue

        constraint = LayoutConstraint(
            layout_name=layout.name,
            layout_type=layout_type,
        )

        first_object_seen = False
        for ph in layout.placeholders:
            ph_type = ph.placeholder_format.type
            ph_idx = ph.placeholder_format.idx

            if ph_type in _PH_SKIP:
                continue

            w_cm = _emu_to_cm(ph.width) if ph.width else 0
            h_cm = _emu_to_cm(ph.height) if ph.height else 0

            # Get font sizes from XML; fall back to sensible defaults
            font_sizes = _get_font_sizes_from_xml(ph._element)
            if font_sizes:
                # Use the largest for titles, smallest for body content
                if ph_type == _PH_TITLE:
                    font_pt = max(font_sizes)
                else:
                    font_pt = min(font_sizes)
            else:
                font_pt = 28.0 if ph_type == _PH_TITLE else 18.0

            role = _ph_role(ph_type, layout_type, not first_object_seen)
            if ph_type == _PH_OBJECT:
                first_object_seen = True

            max_lines, max_chars = _estimate_capacity(w_cm, h_cm, font_pt)

            constraint.placeholders.append(PlaceholderConstraint(
                role=role,
                width_cm=w_cm,
                height_cm=h_cm,
                font_size_pt=font_pt,
                max_lines=max_lines,
                max_chars_per_line=max_chars,
            ))

            # Set top-level convenience fields
            if role == "title":
                constraint.title_max_chars = max_chars
            elif role == "content":
                constraint.max_bullets = max_lines
                constraint.max_chars_per_bullet = max_chars

        theme.layout_constraints.append(constraint)

    logger.debug(
        f"Layout constraints: {[(c.layout_type, c.max_bullets, c.max_chars_per_bullet) for c in theme.layout_constraints]}"
    )


def theme_to_css(theme: TemplateTheme) -> str:
    """Generate custom CSS that approximates the template's visual style."""
    return f"""
    /* Template Theme: {theme.template_name or theme.template_id} */
    section {{
      font-family: '{theme.body_font}', sans-serif !important;
      color: {theme.text_color} !important;
      background-color: {theme.bg_color} !important;
    }}
    section h1, section h2, section h3 {{
      font-family: '{theme.heading_font}', sans-serif !important;
      color: {theme.heading_color} !important;
    }}
    section h1 {{
      border-bottom: 3px solid {theme.accent_color} !important;
      padding-bottom: 0.2em !important;
    }}
    section ul li::marker, section ol li::marker {{
      color: {theme.accent_color};
    }}
    section strong {{
      color: {theme.accent_color};
    }}
    section a {{
      color: {theme.accent_color};
    }}
    section blockquote {{
      border-left-color: {theme.accent2_color} !important;
    }}
    section code {{
      background-color: {theme.accent_color}15 !important;
    }}
    """
