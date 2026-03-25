"""Layout blueprints for all 14 slide types.

Each blueprint defines element positions in cm on a standard 25.4 x 19.05 cm slide (widescreen 16:9).
The LayoutEngine applies audience/style modifiers to these base values.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from app.schemas.models import SlideType


@dataclass
class ElementBlueprint:
    """One visual element on a slide."""
    key: str                      # e.g. "headline", "bullet_area", "kpi_0"
    x_cm: float = 0.0
    y_cm: float = 0.0
    w_cm: float = 0.0
    h_cm: float = 0.0
    font_size_pt: int = 18
    font_color: str = "#333333"
    bold: bool = False
    alignment: str = "left"       # left, center, right
    v_alignment: str = "top"      # top, middle, bottom
    line_spacing: float = 1.15
    is_shape: bool = False        # True for accent bars, dividers, etc.
    shape_fill: str = ""          # hex color or "accent" placeholder
    corner_radius_cm: float = 0.0


@dataclass
class SlideBlueprint:
    """Complete layout blueprint for one slide type."""
    slide_type: SlideType
    elements: list[ElementBlueprint] = field(default_factory=list)
    background: str = "#FFFFFF"   # hex or "accent_dark"
    notes: str = ""


# ── Standard measurements ──
_SL_W = 25.4   # slide width cm
_SL_H = 19.05  # slide height cm
_PAD = 1.8     # standard side padding
_TOP = 1.5     # standard top padding
_HDL_H = 2.5   # headline height
_BODY_TOP = 4.8  # where body content starts


def _headline(x: float = _PAD, y: float = _TOP, w: float = _SL_W - 2 * _PAD,
              h: float = _HDL_H, size: int = 28, align: str = "left") -> ElementBlueprint:
    return ElementBlueprint(
        key="headline", x_cm=x, y_cm=y, w_cm=w, h_cm=h,
        font_size_pt=size, bold=True, alignment=align, font_color="#1a1a2e",
    )


def _subheadline(x: float = _PAD, y: float = _TOP + _HDL_H + 0.2,
                 w: float = _SL_W - 2 * _PAD) -> ElementBlueprint:
    return ElementBlueprint(
        key="subheadline", x_cm=x, y_cm=y, w_cm=w, h_cm=1.8,
        font_size_pt=18, font_color="#6b7280",
    )


# ---------------------------------------------------------------------------
# Blueprint definitions
# ---------------------------------------------------------------------------

_TITLE_HERO = SlideBlueprint(
    slide_type=SlideType.TITLE_HERO,
    background="accent_dark",
    elements=[
        ElementBlueprint(key="accent_bar", x_cm=_PAD, y_cm=7.0, w_cm=4.0, h_cm=0.18,
                         is_shape=True, shape_fill="accent"),
        ElementBlueprint(key="headline", x_cm=_PAD, y_cm=7.8, w_cm=21.0, h_cm=4.5,
                         font_size_pt=44, bold=True, font_color="#FFFFFF", alignment="left"),
        ElementBlueprint(key="subheadline", x_cm=_PAD, y_cm=12.8, w_cm=21.0, h_cm=2.2,
                         font_size_pt=22, font_color="#d1d5db"),
    ],
)

_SECTION_DIVIDER = SlideBlueprint(
    slide_type=SlideType.SECTION_DIVIDER,
    background="accent_dark",
    elements=[
        ElementBlueprint(key="headline", x_cm=_PAD, y_cm=6.5, w_cm=_SL_W - 2 * _PAD, h_cm=4.5,
                         font_size_pt=40, bold=True, font_color="#FFFFFF", alignment="center"),
        ElementBlueprint(key="accent_bar", x_cm=10.5, y_cm=12.0, w_cm=4.4, h_cm=0.2,
                         is_shape=True, shape_fill="accent"),
    ],
)

_KEY_STATEMENT = SlideBlueprint(
    slide_type=SlideType.KEY_STATEMENT,
    elements=[
        ElementBlueprint(key="quote_mark", x_cm=2.5, y_cm=3.5, w_cm=4.0, h_cm=4.0,
                         is_shape=True, shape_fill="accent_light", font_size_pt=120,
                         font_color="#e5e7eb"),
        ElementBlueprint(key="statement", x_cm=4.0, y_cm=5.0, w_cm=17.5, h_cm=6.5,
                         font_size_pt=32, bold=True, alignment="left",
                         line_spacing=1.4, font_color="#1a1a2e"),
        ElementBlueprint(key="attribution", x_cm=4.0, y_cm=12.5, w_cm=17.5, h_cm=1.5,
                         font_size_pt=16, font_color="#9ca3af"),
    ],
)

_BULLETS_FOCUSED = SlideBlueprint(
    slide_type=SlideType.BULLETS_FOCUSED,
    elements=[
        _headline(),
        ElementBlueprint(key="bullet_area", x_cm=_PAD, y_cm=_BODY_TOP, w_cm=15.0, h_cm=11.0,
                         font_size_pt=18, line_spacing=1.6, font_color="#374151"),
    ],
)

_THREE_CARDS = SlideBlueprint(
    slide_type=SlideType.THREE_CARDS,
    elements=[
        _headline(),
        # 3 cards calculated dynamically; these are placeholders for card area
        ElementBlueprint(key="card_0", x_cm=_PAD, y_cm=_BODY_TOP, w_cm=6.8, h_cm=11.5,
                         is_shape=True, shape_fill="#f3f4f6", corner_radius_cm=0.35),
        ElementBlueprint(key="card_1", x_cm=_PAD + 7.4, y_cm=_BODY_TOP, w_cm=6.8, h_cm=11.5,
                         is_shape=True, shape_fill="#f3f4f6", corner_radius_cm=0.35),
        ElementBlueprint(key="card_2", x_cm=_PAD + 14.8, y_cm=_BODY_TOP, w_cm=6.8, h_cm=11.5,
                         is_shape=True, shape_fill="#f3f4f6", corner_radius_cm=0.35),
        # Card titles (inside cards)
        ElementBlueprint(key="card_title_0", x_cm=_PAD + 0.6, y_cm=_BODY_TOP + 2.8,
                         w_cm=5.6, h_cm=1.5, font_size_pt=18, bold=True, alignment="center",
                         font_color="#1a1a2e"),
        ElementBlueprint(key="card_title_1", x_cm=_PAD + 8.0, y_cm=_BODY_TOP + 2.8,
                         w_cm=5.6, h_cm=1.5, font_size_pt=18, bold=True, alignment="center",
                         font_color="#1a1a2e"),
        ElementBlueprint(key="card_title_2", x_cm=_PAD + 15.4, y_cm=_BODY_TOP + 2.8,
                         w_cm=5.6, h_cm=1.5, font_size_pt=18, bold=True, alignment="center",
                         font_color="#1a1a2e"),
        # Card bodies
        ElementBlueprint(key="card_body_0", x_cm=_PAD + 0.6, y_cm=_BODY_TOP + 4.6,
                         w_cm=5.6, h_cm=5.5, font_size_pt=14, font_color="#4b5563",
                         alignment="center", line_spacing=1.35),
        ElementBlueprint(key="card_body_1", x_cm=_PAD + 8.0, y_cm=_BODY_TOP + 4.6,
                         w_cm=5.6, h_cm=5.5, font_size_pt=14, font_color="#4b5563",
                         alignment="center", line_spacing=1.35),
        ElementBlueprint(key="card_body_2", x_cm=_PAD + 15.4, y_cm=_BODY_TOP + 4.6,
                         w_cm=5.6, h_cm=5.5, font_size_pt=14, font_color="#4b5563",
                         alignment="center", line_spacing=1.35),
        # Card icons (emoji/icon area)
        ElementBlueprint(key="card_icon_0", x_cm=_PAD + 0.6, y_cm=_BODY_TOP + 0.6,
                         w_cm=5.6, h_cm=2.0, font_size_pt=32, alignment="center"),
        ElementBlueprint(key="card_icon_1", x_cm=_PAD + 8.0, y_cm=_BODY_TOP + 0.6,
                         w_cm=5.6, h_cm=2.0, font_size_pt=32, alignment="center"),
        ElementBlueprint(key="card_icon_2", x_cm=_PAD + 15.4, y_cm=_BODY_TOP + 0.6,
                         w_cm=5.6, h_cm=2.0, font_size_pt=32, alignment="center"),
    ],
)

_KPI_DASHBOARD = SlideBlueprint(
    slide_type=SlideType.KPI_DASHBOARD,
    elements=[
        _headline(),
        # KPI cards — up to 5, positioned dynamically by engine
        # Base positions for a 3-KPI layout (most common)
        ElementBlueprint(key="kpi_card_0", x_cm=_PAD, y_cm=_BODY_TOP + 0.5,
                         w_cm=6.8, h_cm=8.0, is_shape=True, shape_fill="#f3f4f6",
                         corner_radius_cm=0.35),
        ElementBlueprint(key="kpi_card_1", x_cm=_PAD + 7.4, y_cm=_BODY_TOP + 0.5,
                         w_cm=6.8, h_cm=8.0, is_shape=True, shape_fill="#f3f4f6",
                         corner_radius_cm=0.35),
        ElementBlueprint(key="kpi_card_2", x_cm=_PAD + 14.8, y_cm=_BODY_TOP + 0.5,
                         w_cm=6.8, h_cm=8.0, is_shape=True, shape_fill="#f3f4f6",
                         corner_radius_cm=0.35),
        # KPI values (large numbers)
        ElementBlueprint(key="kpi_value_0", x_cm=_PAD + 0.5, y_cm=_BODY_TOP + 1.5,
                         w_cm=5.8, h_cm=3.0, font_size_pt=40, bold=True,
                         alignment="center", font_color="#1a1a2e"),
        ElementBlueprint(key="kpi_value_1", x_cm=_PAD + 7.9, y_cm=_BODY_TOP + 1.5,
                         w_cm=5.8, h_cm=3.0, font_size_pt=40, bold=True,
                         alignment="center", font_color="#1a1a2e"),
        ElementBlueprint(key="kpi_value_2", x_cm=_PAD + 15.3, y_cm=_BODY_TOP + 1.5,
                         w_cm=5.8, h_cm=3.0, font_size_pt=40, bold=True,
                         alignment="center", font_color="#1a1a2e"),
        # KPI labels
        ElementBlueprint(key="kpi_label_0", x_cm=_PAD + 0.5, y_cm=_BODY_TOP + 5.0,
                         w_cm=5.8, h_cm=1.5, font_size_pt=14, alignment="center",
                         font_color="#6b7280"),
        ElementBlueprint(key="kpi_label_1", x_cm=_PAD + 7.9, y_cm=_BODY_TOP + 5.0,
                         w_cm=5.8, h_cm=1.5, font_size_pt=14, alignment="center",
                         font_color="#6b7280"),
        ElementBlueprint(key="kpi_label_2", x_cm=_PAD + 15.3, y_cm=_BODY_TOP + 5.0,
                         w_cm=5.8, h_cm=1.5, font_size_pt=14, alignment="center",
                         font_color="#6b7280"),
        # KPI deltas
        ElementBlueprint(key="kpi_delta_0", x_cm=_PAD + 0.5, y_cm=_BODY_TOP + 6.5,
                         w_cm=5.8, h_cm=1.2, font_size_pt=16, bold=True,
                         alignment="center", font_color="#22c55e"),
        ElementBlueprint(key="kpi_delta_1", x_cm=_PAD + 7.9, y_cm=_BODY_TOP + 6.5,
                         w_cm=5.8, h_cm=1.2, font_size_pt=16, bold=True,
                         alignment="center", font_color="#22c55e"),
        ElementBlueprint(key="kpi_delta_2", x_cm=_PAD + 15.3, y_cm=_BODY_TOP + 6.5,
                         w_cm=5.8, h_cm=1.2, font_size_pt=16, bold=True,
                         alignment="center", font_color="#22c55e"),
    ],
)

_IMAGE_TEXT_SPLIT = SlideBlueprint(
    slide_type=SlideType.IMAGE_TEXT_SPLIT,
    elements=[
        ElementBlueprint(key="headline", x_cm=_PAD, y_cm=_TOP, w_cm=11.5, h_cm=_HDL_H,
                         font_size_pt=28, bold=True, font_color="#1a1a2e"),
        ElementBlueprint(key="body_area", x_cm=_PAD, y_cm=_BODY_TOP, w_cm=11.5, h_cm=11.0,
                         font_size_pt=16, font_color="#374151", line_spacing=1.5),
        ElementBlueprint(key="image_area", x_cm=14.0, y_cm=0, w_cm=11.4, h_cm=_SL_H),
    ],
)

_COMPARISON = SlideBlueprint(
    slide_type=SlideType.COMPARISON,
    elements=[
        _headline(),
        # Left column
        ElementBlueprint(key="col_left_bg", x_cm=_PAD, y_cm=_BODY_TOP,
                         w_cm=10.5, h_cm=12.0, is_shape=True, shape_fill="#f3f4f6",
                         corner_radius_cm=0.3),
        ElementBlueprint(key="col_left_label", x_cm=_PAD + 0.6, y_cm=_BODY_TOP + 0.5,
                         w_cm=9.3, h_cm=1.8, font_size_pt=20, bold=True,
                         font_color="#1a1a2e", alignment="center"),
        ElementBlueprint(key="col_left_body", x_cm=_PAD + 0.6, y_cm=_BODY_TOP + 2.8,
                         w_cm=9.3, h_cm=8.5, font_size_pt=15, font_color="#374151",
                         line_spacing=1.5),
        # Divider
        ElementBlueprint(key="divider", x_cm=12.7, y_cm=_BODY_TOP + 0.5,
                         w_cm=0.06, h_cm=11.0, is_shape=True, shape_fill="#d1d5db"),
        # Right column
        ElementBlueprint(key="col_right_bg", x_cm=13.1, y_cm=_BODY_TOP,
                         w_cm=10.5, h_cm=12.0, is_shape=True, shape_fill="#f3f4f6",
                         corner_radius_cm=0.3),
        ElementBlueprint(key="col_right_label", x_cm=13.7, y_cm=_BODY_TOP + 0.5,
                         w_cm=9.3, h_cm=1.8, font_size_pt=20, bold=True,
                         font_color="#1a1a2e", alignment="center"),
        ElementBlueprint(key="col_right_body", x_cm=13.7, y_cm=_BODY_TOP + 2.8,
                         w_cm=9.3, h_cm=8.5, font_size_pt=15, font_color="#374151",
                         line_spacing=1.5),
    ],
)

_TIMELINE = SlideBlueprint(
    slide_type=SlideType.TIMELINE,
    elements=[
        _headline(),
        # Timeline track (horizontal line)
        ElementBlueprint(key="track_line", x_cm=_PAD, y_cm=9.5,
                         w_cm=_SL_W - 2 * _PAD, h_cm=0.1,
                         is_shape=True, shape_fill="#d1d5db"),
        # Timeline nodes — dynamically positioned by engine based on entry count
        # These are template positions for up to 5 entries
        ElementBlueprint(key="node_0", x_cm=3.0, y_cm=9.1, w_cm=0.9, h_cm=0.9,
                         is_shape=True, shape_fill="accent", corner_radius_cm=0.45),
        ElementBlueprint(key="node_1", x_cm=7.5, y_cm=9.1, w_cm=0.9, h_cm=0.9,
                         is_shape=True, shape_fill="accent", corner_radius_cm=0.45),
        ElementBlueprint(key="node_2", x_cm=12.0, y_cm=9.1, w_cm=0.9, h_cm=0.9,
                         is_shape=True, shape_fill="accent", corner_radius_cm=0.45),
        ElementBlueprint(key="node_3", x_cm=16.5, y_cm=9.1, w_cm=0.9, h_cm=0.9,
                         is_shape=True, shape_fill="accent", corner_radius_cm=0.45),
        ElementBlueprint(key="node_4", x_cm=21.0, y_cm=9.1, w_cm=0.9, h_cm=0.9,
                         is_shape=True, shape_fill="accent", corner_radius_cm=0.45),
        # Date labels (above track)
        ElementBlueprint(key="date_0", x_cm=1.5, y_cm=7.5, w_cm=3.9, h_cm=1.2,
                         font_size_pt=12, font_color="accent", bold=True, alignment="center"),
        ElementBlueprint(key="date_1", x_cm=6.0, y_cm=7.5, w_cm=3.9, h_cm=1.2,
                         font_size_pt=12, font_color="accent", bold=True, alignment="center"),
        ElementBlueprint(key="date_2", x_cm=10.5, y_cm=7.5, w_cm=3.9, h_cm=1.2,
                         font_size_pt=12, font_color="accent", bold=True, alignment="center"),
        ElementBlueprint(key="date_3", x_cm=15.0, y_cm=7.5, w_cm=3.9, h_cm=1.2,
                         font_size_pt=12, font_color="accent", bold=True, alignment="center"),
        ElementBlueprint(key="date_4", x_cm=19.5, y_cm=7.5, w_cm=3.9, h_cm=1.2,
                         font_size_pt=12, font_color="accent", bold=True, alignment="center"),
        # Title labels (below track)
        ElementBlueprint(key="entry_title_0", x_cm=1.5, y_cm=10.5, w_cm=3.9, h_cm=1.5,
                         font_size_pt=14, bold=True, alignment="center", font_color="#1a1a2e"),
        ElementBlueprint(key="entry_title_1", x_cm=6.0, y_cm=10.5, w_cm=3.9, h_cm=1.5,
                         font_size_pt=14, bold=True, alignment="center", font_color="#1a1a2e"),
        ElementBlueprint(key="entry_title_2", x_cm=10.5, y_cm=10.5, w_cm=3.9, h_cm=1.5,
                         font_size_pt=14, bold=True, alignment="center", font_color="#1a1a2e"),
        ElementBlueprint(key="entry_title_3", x_cm=15.0, y_cm=10.5, w_cm=3.9, h_cm=1.5,
                         font_size_pt=14, bold=True, alignment="center", font_color="#1a1a2e"),
        ElementBlueprint(key="entry_title_4", x_cm=19.5, y_cm=10.5, w_cm=3.9, h_cm=1.5,
                         font_size_pt=14, bold=True, alignment="center", font_color="#1a1a2e"),
        # Description labels
        ElementBlueprint(key="entry_desc_0", x_cm=1.5, y_cm=12.0, w_cm=3.9, h_cm=3.0,
                         font_size_pt=11, font_color="#6b7280", alignment="center"),
        ElementBlueprint(key="entry_desc_1", x_cm=6.0, y_cm=12.0, w_cm=3.9, h_cm=3.0,
                         font_size_pt=11, font_color="#6b7280", alignment="center"),
        ElementBlueprint(key="entry_desc_2", x_cm=10.5, y_cm=12.0, w_cm=3.9, h_cm=3.0,
                         font_size_pt=11, font_color="#6b7280", alignment="center"),
        ElementBlueprint(key="entry_desc_3", x_cm=15.0, y_cm=12.0, w_cm=3.9, h_cm=3.0,
                         font_size_pt=11, font_color="#6b7280", alignment="center"),
        ElementBlueprint(key="entry_desc_4", x_cm=19.5, y_cm=12.0, w_cm=3.9, h_cm=3.0,
                         font_size_pt=11, font_color="#6b7280", alignment="center"),
    ],
)

_PROCESS_FLOW = SlideBlueprint(
    slide_type=SlideType.PROCESS_FLOW,
    elements=[
        _headline(),
        # Process steps — dynamically positioned. Template for 4 steps:
        ElementBlueprint(key="step_box_0", x_cm=_PAD, y_cm=_BODY_TOP + 0.5,
                         w_cm=4.8, h_cm=10.5, is_shape=True, shape_fill="#eef2ff",
                         corner_radius_cm=0.3),
        ElementBlueprint(key="step_box_1", x_cm=_PAD + 5.5, y_cm=_BODY_TOP + 0.5,
                         w_cm=4.8, h_cm=10.5, is_shape=True, shape_fill="#eef2ff",
                         corner_radius_cm=0.3),
        ElementBlueprint(key="step_box_2", x_cm=_PAD + 11.0, y_cm=_BODY_TOP + 0.5,
                         w_cm=4.8, h_cm=10.5, is_shape=True, shape_fill="#eef2ff",
                         corner_radius_cm=0.3),
        ElementBlueprint(key="step_box_3", x_cm=_PAD + 16.5, y_cm=_BODY_TOP + 0.5,
                         w_cm=4.8, h_cm=10.5, is_shape=True, shape_fill="#eef2ff",
                         corner_radius_cm=0.3),
        # Step numbers (circles)
        ElementBlueprint(key="step_num_0", x_cm=_PAD + 1.6, y_cm=_BODY_TOP + 1.2,
                         w_cm=1.6, h_cm=1.6, is_shape=True, shape_fill="accent",
                         corner_radius_cm=0.8, font_size_pt=20, font_color="#FFFFFF",
                         bold=True, alignment="center"),
        ElementBlueprint(key="step_num_1", x_cm=_PAD + 7.1, y_cm=_BODY_TOP + 1.2,
                         w_cm=1.6, h_cm=1.6, is_shape=True, shape_fill="accent",
                         corner_radius_cm=0.8, font_size_pt=20, font_color="#FFFFFF",
                         bold=True, alignment="center"),
        ElementBlueprint(key="step_num_2", x_cm=_PAD + 12.6, y_cm=_BODY_TOP + 1.2,
                         w_cm=1.6, h_cm=1.6, is_shape=True, shape_fill="accent",
                         corner_radius_cm=0.8, font_size_pt=20, font_color="#FFFFFF",
                         bold=True, alignment="center"),
        ElementBlueprint(key="step_num_3", x_cm=_PAD + 18.1, y_cm=_BODY_TOP + 1.2,
                         w_cm=1.6, h_cm=1.6, is_shape=True, shape_fill="accent",
                         corner_radius_cm=0.8, font_size_pt=20, font_color="#FFFFFF",
                         bold=True, alignment="center"),
        # Step titles
        ElementBlueprint(key="step_title_0", x_cm=_PAD + 0.4, y_cm=_BODY_TOP + 3.5,
                         w_cm=4.0, h_cm=1.5, font_size_pt=16, bold=True,
                         alignment="center", font_color="#1a1a2e"),
        ElementBlueprint(key="step_title_1", x_cm=_PAD + 5.9, y_cm=_BODY_TOP + 3.5,
                         w_cm=4.0, h_cm=1.5, font_size_pt=16, bold=True,
                         alignment="center", font_color="#1a1a2e"),
        ElementBlueprint(key="step_title_2", x_cm=_PAD + 11.4, y_cm=_BODY_TOP + 3.5,
                         w_cm=4.0, h_cm=1.5, font_size_pt=16, bold=True,
                         alignment="center", font_color="#1a1a2e"),
        ElementBlueprint(key="step_title_3", x_cm=_PAD + 16.9, y_cm=_BODY_TOP + 3.5,
                         w_cm=4.0, h_cm=1.5, font_size_pt=16, bold=True,
                         alignment="center", font_color="#1a1a2e"),
        # Step descriptions
        ElementBlueprint(key="step_desc_0", x_cm=_PAD + 0.4, y_cm=_BODY_TOP + 5.2,
                         w_cm=4.0, h_cm=5.0, font_size_pt=12, font_color="#4b5563",
                         alignment="center", line_spacing=1.3),
        ElementBlueprint(key="step_desc_1", x_cm=_PAD + 5.9, y_cm=_BODY_TOP + 5.2,
                         w_cm=4.0, h_cm=5.0, font_size_pt=12, font_color="#4b5563",
                         alignment="center", line_spacing=1.3),
        ElementBlueprint(key="step_desc_2", x_cm=_PAD + 11.4, y_cm=_BODY_TOP + 5.2,
                         w_cm=4.0, h_cm=5.0, font_size_pt=12, font_color="#4b5563",
                         alignment="center", line_spacing=1.3),
        ElementBlueprint(key="step_desc_3", x_cm=_PAD + 16.9, y_cm=_BODY_TOP + 5.2,
                         w_cm=4.0, h_cm=5.0, font_size_pt=12, font_color="#4b5563",
                         alignment="center", line_spacing=1.3),
        # Arrows between steps
        ElementBlueprint(key="arrow_0", x_cm=_PAD + 5.0, y_cm=_BODY_TOP + 1.7,
                         w_cm=0.4, h_cm=0.6, is_shape=True, shape_fill="accent"),
        ElementBlueprint(key="arrow_1", x_cm=_PAD + 10.5, y_cm=_BODY_TOP + 1.7,
                         w_cm=0.4, h_cm=0.6, is_shape=True, shape_fill="accent"),
        ElementBlueprint(key="arrow_2", x_cm=_PAD + 16.0, y_cm=_BODY_TOP + 1.7,
                         w_cm=0.4, h_cm=0.6, is_shape=True, shape_fill="accent"),
    ],
)

_CHART_INSIGHT = SlideBlueprint(
    slide_type=SlideType.CHART_INSIGHT,
    elements=[
        _headline(),
        ElementBlueprint(key="chart_area", x_cm=_PAD, y_cm=_BODY_TOP,
                         w_cm=16.0, h_cm=12.0),
        ElementBlueprint(key="takeaway_area", x_cm=18.5, y_cm=_BODY_TOP,
                         w_cm=5.5, h_cm=12.0, font_size_pt=14, font_color="#6b7280",
                         line_spacing=1.4),
    ],
)

_IMAGE_FULLBLEED = SlideBlueprint(
    slide_type=SlideType.IMAGE_FULLBLEED,
    elements=[
        ElementBlueprint(key="background_image", x_cm=0, y_cm=0,
                         w_cm=_SL_W, h_cm=_SL_H),
        ElementBlueprint(key="overlay_bg", x_cm=0, y_cm=13.0,
                         w_cm=_SL_W, h_cm=6.05, is_shape=True,
                         shape_fill="#000000"),  # 50% opacity applied in renderer
        ElementBlueprint(key="headline", x_cm=_PAD, y_cm=13.8,
                         w_cm=_SL_W - 2 * _PAD, h_cm=3.5,
                         font_size_pt=32, bold=True, font_color="#FFFFFF"),
    ],
)

_AGENDA = SlideBlueprint(
    slide_type=SlideType.AGENDA,
    elements=[
        _headline(size=32),
        ElementBlueprint(key="agenda_list", x_cm=_PAD, y_cm=_BODY_TOP + 0.5,
                         w_cm=15.0, h_cm=12.0, font_size_pt=20, font_color="#374151",
                         line_spacing=2.0),
    ],
)

_CLOSING = SlideBlueprint(
    slide_type=SlideType.CLOSING,
    elements=[
        ElementBlueprint(key="headline", x_cm=_PAD, y_cm=4.5,
                         w_cm=_SL_W - 2 * _PAD, h_cm=4.0,
                         font_size_pt=36, bold=True, alignment="center",
                         font_color="#1a1a2e"),
        ElementBlueprint(key="takeaways", x_cm=4.0, y_cm=9.5,
                         w_cm=17.4, h_cm=5.5, font_size_pt=18,
                         alignment="center", font_color="#374151", line_spacing=1.6),
        ElementBlueprint(key="contact", x_cm=4.0, y_cm=16.0,
                         w_cm=17.4, h_cm=2.0, font_size_pt=14,
                         alignment="center", font_color="#9ca3af"),
    ],
)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

BLUEPRINTS: dict[SlideType, SlideBlueprint] = {
    SlideType.TITLE_HERO: _TITLE_HERO,
    SlideType.SECTION_DIVIDER: _SECTION_DIVIDER,
    SlideType.KEY_STATEMENT: _KEY_STATEMENT,
    SlideType.BULLETS_FOCUSED: _BULLETS_FOCUSED,
    SlideType.THREE_CARDS: _THREE_CARDS,
    SlideType.KPI_DASHBOARD: _KPI_DASHBOARD,
    SlideType.IMAGE_TEXT_SPLIT: _IMAGE_TEXT_SPLIT,
    SlideType.COMPARISON: _COMPARISON,
    SlideType.TIMELINE: _TIMELINE,
    SlideType.PROCESS_FLOW: _PROCESS_FLOW,
    SlideType.CHART_INSIGHT: _CHART_INSIGHT,
    SlideType.IMAGE_FULLBLEED: _IMAGE_FULLBLEED,
    SlideType.AGENDA: _AGENDA,
    SlideType.CLOSING: _CLOSING,
}


def get_blueprint(slide_type: SlideType) -> SlideBlueprint:
    bp = BLUEPRINTS.get(slide_type)
    if bp is None:
        return BLUEPRINTS[SlideType.BULLETS_FOCUSED]
    return bp
