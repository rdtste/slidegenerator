"""Layout blueprints for all 14 slide types.

Each blueprint defines element positions in cm on a standard 25.4 x 19.05 cm slide (widescreen 16:9).
The LayoutEngine applies audience/style modifiers to these base values.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from app.schemas.models import SlideType
from app.design_tokens import DEFAULT_TOKENS

_t = DEFAULT_TOKENS


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


# ── Standard measurements (from design tokens) ──
_SL_W = _t.spacing.slide_width
_SL_H = _t.spacing.slide_height
_PAD = _t.spacing.side_padding
_TOP = _t.spacing.top_padding
_HDL_H = _t.spacing.headline_height
_BODY_TOP = _t.spacing.body_top
_GAP = _t.spacing.content_gap


def _headline(x: float = _PAD, y: float = _TOP, w: float = _SL_W - 2 * _PAD,
              h: float = _HDL_H, size: int = 0, align: str = "left") -> ElementBlueprint:
    return ElementBlueprint(
        key="headline", x_cm=x, y_cm=y, w_cm=w, h_cm=h,
        font_size_pt=size or _t.typography.slide_headline,
        bold=True, alignment=align, font_color=_t.colors.headline,
    )


def _subheadline(x: float = _PAD, y: float = _TOP + _HDL_H + 0.2,
                 w: float = _SL_W - 2 * _PAD) -> ElementBlueprint:
    return ElementBlueprint(
        key="subheadline", x_cm=x, y_cm=y, w_cm=w, h_cm=1.8,
        font_size_pt=_t.typography.subheadline_small, font_color=_t.colors.muted,
    )


# ---------------------------------------------------------------------------
# Blueprint definitions
# ---------------------------------------------------------------------------

_TITLE_HERO = SlideBlueprint(
    slide_type=SlideType.TITLE_HERO,
    background="accent_dark",
    elements=[
        ElementBlueprint(key="accent_bar", x_cm=_PAD, y_cm=7.0, w_cm=4.0,
                         h_cm=_t.spacing.accent_bar_height,
                         is_shape=True, shape_fill="accent"),
        ElementBlueprint(key="headline", x_cm=_PAD, y_cm=7.8, w_cm=21.0, h_cm=4.5,
                         font_size_pt=_t.typography.hero_title, bold=True,
                         font_color=_t.colors.text_on_dark, alignment="left"),
        ElementBlueprint(key="subheadline", x_cm=_PAD, y_cm=12.8, w_cm=21.0, h_cm=2.2,
                         font_size_pt=_t.typography.subheadline,
                         font_color=_t.colors.text_on_dark_muted),
    ],
)

_SECTION_DIVIDER = SlideBlueprint(
    slide_type=SlideType.SECTION_DIVIDER,
    background="accent_dark",
    elements=[
        ElementBlueprint(key="headline", x_cm=_PAD, y_cm=6.5, w_cm=_SL_W - 2 * _PAD, h_cm=4.5,
                         font_size_pt=_t.typography.section_title, bold=True,
                         font_color=_t.colors.text_on_dark, alignment="center"),
        ElementBlueprint(key="accent_bar", x_cm=10.5, y_cm=12.0, w_cm=4.4, h_cm=0.2,
                         is_shape=True, shape_fill="accent"),
    ],
)

_KEY_STATEMENT = SlideBlueprint(
    slide_type=SlideType.KEY_STATEMENT,
    elements=[
        ElementBlueprint(key="quote_mark", x_cm=2.5, y_cm=3.5, w_cm=4.0, h_cm=4.0,
                         is_shape=True, shape_fill="accent_light",
                         font_size_pt=_t.typography.quote_mark,
                         font_color=_t.colors.quote_mark),
        ElementBlueprint(key="statement", x_cm=4.0, y_cm=5.0, w_cm=17.5, h_cm=6.5,
                         font_size_pt=_t.typography.statement_text, bold=True, alignment="left",
                         line_spacing=_t.typography.spacing_statement,
                         font_color=_t.colors.headline),
        ElementBlueprint(key="attribution", x_cm=4.0, y_cm=12.5, w_cm=17.5, h_cm=1.5,
                         font_size_pt=_t.typography.attribution,
                         font_color=_t.colors.subtle),
    ],
)

_BULLETS_FOCUSED = SlideBlueprint(
    slide_type=SlideType.BULLETS_FOCUSED,
    elements=[
        _headline(),
        ElementBlueprint(key="bullet_area", x_cm=_PAD, y_cm=_BODY_TOP + 0.5, w_cm=14.0, h_cm=10.0,
                         font_size_pt=_t.typography.body_default,
                         line_spacing=_t.typography.spacing_bullets,
                         font_color=_t.colors.body),
    ],
)

_CARD_W = _t.spacing.card_width
_CARD_GAP = _t.spacing.card_gap
_CARD_INNER = _t.spacing.card_inner_padding

_THREE_CARDS = SlideBlueprint(
    slide_type=SlideType.THREE_CARDS,
    elements=[
        _headline(),
        # 3 cards with generous gaps between them
        ElementBlueprint(key="card_0", x_cm=_PAD, y_cm=_BODY_TOP, w_cm=_CARD_W, h_cm=10.5,
                         is_shape=True, shape_fill=_t.colors.card_bg,
                         corner_radius_cm=_t.spacing.card_corner_radius),
        ElementBlueprint(key="card_1", x_cm=_PAD + _CARD_W + _CARD_GAP, y_cm=_BODY_TOP,
                         w_cm=_CARD_W, h_cm=10.5,
                         is_shape=True, shape_fill=_t.colors.card_bg,
                         corner_radius_cm=_t.spacing.card_corner_radius),
        ElementBlueprint(key="card_2", x_cm=_PAD + 2 * (_CARD_W + _CARD_GAP), y_cm=_BODY_TOP,
                         w_cm=_CARD_W, h_cm=10.5,
                         is_shape=True, shape_fill=_t.colors.card_bg,
                         corner_radius_cm=_t.spacing.card_corner_radius),
        # Card icons — larger, more prominent
        ElementBlueprint(key="card_icon_0", x_cm=_PAD + _CARD_INNER, y_cm=_BODY_TOP + 0.8,
                         w_cm=_CARD_W - 2 * _CARD_INNER, h_cm=2.2,
                         font_size_pt=_t.typography.card_icon, alignment="center"),
        ElementBlueprint(key="card_icon_1", x_cm=_PAD + _CARD_W + _CARD_GAP + _CARD_INNER,
                         y_cm=_BODY_TOP + 0.8,
                         w_cm=_CARD_W - 2 * _CARD_INNER, h_cm=2.2,
                         font_size_pt=_t.typography.card_icon, alignment="center"),
        ElementBlueprint(key="card_icon_2", x_cm=_PAD + 2 * (_CARD_W + _CARD_GAP) + _CARD_INNER,
                         y_cm=_BODY_TOP + 0.8,
                         w_cm=_CARD_W - 2 * _CARD_INNER, h_cm=2.2,
                         font_size_pt=_t.typography.card_icon, alignment="center"),
        # Card titles — bold, clear hierarchy
        ElementBlueprint(key="card_title_0", x_cm=_PAD + _CARD_INNER, y_cm=_BODY_TOP + 3.2,
                         w_cm=_CARD_W - 2 * _CARD_INNER, h_cm=1.4,
                         font_size_pt=_t.typography.card_title, bold=True,
                         alignment="center", font_color=_t.colors.headline),
        ElementBlueprint(key="card_title_1", x_cm=_PAD + _CARD_W + _CARD_GAP + _CARD_INNER,
                         y_cm=_BODY_TOP + 3.2,
                         w_cm=_CARD_W - 2 * _CARD_INNER, h_cm=1.4,
                         font_size_pt=_t.typography.card_title, bold=True,
                         alignment="center", font_color=_t.colors.headline),
        ElementBlueprint(key="card_title_2", x_cm=_PAD + 2 * (_CARD_W + _CARD_GAP) + _CARD_INNER,
                         y_cm=_BODY_TOP + 3.2,
                         w_cm=_CARD_W - 2 * _CARD_INNER, h_cm=1.4,
                         font_size_pt=_t.typography.card_title, bold=True,
                         alignment="center", font_color=_t.colors.headline),
        # Card bodies — compact, 1-2 sentences max
        ElementBlueprint(key="card_body_0", x_cm=_PAD + _CARD_INNER, y_cm=_BODY_TOP + 5.0,
                         w_cm=_CARD_W - 2 * _CARD_INNER, h_cm=4.5,
                         font_size_pt=_t.typography.body_card,
                         font_color=_t.colors.body, alignment="center",
                         line_spacing=_t.typography.spacing_relaxed),
        ElementBlueprint(key="card_body_1", x_cm=_PAD + _CARD_W + _CARD_GAP + _CARD_INNER,
                         y_cm=_BODY_TOP + 5.0,
                         w_cm=_CARD_W - 2 * _CARD_INNER, h_cm=4.5,
                         font_size_pt=_t.typography.body_card,
                         font_color=_t.colors.body, alignment="center",
                         line_spacing=_t.typography.spacing_relaxed),
        ElementBlueprint(key="card_body_2", x_cm=_PAD + 2 * (_CARD_W + _CARD_GAP) + _CARD_INNER,
                         y_cm=_BODY_TOP + 5.0,
                         w_cm=_CARD_W - 2 * _CARD_INNER, h_cm=4.5,
                         font_size_pt=_t.typography.body_card,
                         font_color=_t.colors.body, alignment="center",
                         line_spacing=_t.typography.spacing_relaxed),
    ],
)

_KPI_DASHBOARD = SlideBlueprint(
    slide_type=SlideType.KPI_DASHBOARD,
    elements=[
        _headline(),
        # KPI cards — dynamically repositioned by engine. Base for 3 KPIs:
        ElementBlueprint(key="kpi_card_0", x_cm=_PAD, y_cm=_BODY_TOP + 0.8,
                         w_cm=_CARD_W, h_cm=9.0, is_shape=True,
                         shape_fill=_t.colors.card_bg,
                         corner_radius_cm=_t.spacing.card_corner_radius),
        ElementBlueprint(key="kpi_card_1", x_cm=_PAD + _CARD_W + _CARD_GAP, y_cm=_BODY_TOP + 0.8,
                         w_cm=_CARD_W, h_cm=9.0, is_shape=True,
                         shape_fill=_t.colors.card_bg,
                         corner_radius_cm=_t.spacing.card_corner_radius),
        ElementBlueprint(key="kpi_card_2", x_cm=_PAD + 2 * (_CARD_W + _CARD_GAP), y_cm=_BODY_TOP + 0.8,
                         w_cm=_CARD_W, h_cm=9.0, is_shape=True,
                         shape_fill=_t.colors.card_bg,
                         corner_radius_cm=_t.spacing.card_corner_radius),
        # KPI values — large, prominent (value is hero element)
        ElementBlueprint(key="kpi_value_0", x_cm=_PAD + _CARD_INNER, y_cm=_BODY_TOP + 2.0,
                         w_cm=_CARD_W - 2 * _CARD_INNER, h_cm=3.5,
                         font_size_pt=_t.typography.kpi_value, bold=True,
                         alignment="center", font_color=_t.colors.headline,
                         v_alignment="middle"),
        ElementBlueprint(key="kpi_value_1", x_cm=_PAD + _CARD_W + _CARD_GAP + _CARD_INNER,
                         y_cm=_BODY_TOP + 2.0,
                         w_cm=_CARD_W - 2 * _CARD_INNER, h_cm=3.5,
                         font_size_pt=_t.typography.kpi_value, bold=True,
                         alignment="center", font_color=_t.colors.headline,
                         v_alignment="middle"),
        ElementBlueprint(key="kpi_value_2", x_cm=_PAD + 2 * (_CARD_W + _CARD_GAP) + _CARD_INNER,
                         y_cm=_BODY_TOP + 2.0,
                         w_cm=_CARD_W - 2 * _CARD_INNER, h_cm=3.5,
                         font_size_pt=_t.typography.kpi_value, bold=True,
                         alignment="center", font_color=_t.colors.headline,
                         v_alignment="middle"),
        # KPI labels — smaller, below value, clear separation
        ElementBlueprint(key="kpi_label_0", x_cm=_PAD + _CARD_INNER, y_cm=_BODY_TOP + 6.0,
                         w_cm=_CARD_W - 2 * _CARD_INNER, h_cm=1.5,
                         font_size_pt=_t.typography.kpi_label,
                         alignment="center", font_color=_t.colors.muted),
        ElementBlueprint(key="kpi_label_1", x_cm=_PAD + _CARD_W + _CARD_GAP + _CARD_INNER,
                         y_cm=_BODY_TOP + 6.0,
                         w_cm=_CARD_W - 2 * _CARD_INNER, h_cm=1.5,
                         font_size_pt=_t.typography.kpi_label,
                         alignment="center", font_color=_t.colors.muted),
        ElementBlueprint(key="kpi_label_2", x_cm=_PAD + 2 * (_CARD_W + _CARD_GAP) + _CARD_INNER,
                         y_cm=_BODY_TOP + 6.0,
                         w_cm=_CARD_W - 2 * _CARD_INNER, h_cm=1.5,
                         font_size_pt=_t.typography.kpi_label,
                         alignment="center", font_color=_t.colors.muted),
        # KPI deltas — bold trend indicator
        ElementBlueprint(key="kpi_delta_0", x_cm=_PAD + _CARD_INNER, y_cm=_BODY_TOP + 7.8,
                         w_cm=_CARD_W - 2 * _CARD_INNER, h_cm=1.2,
                         font_size_pt=_t.typography.kpi_delta, bold=True,
                         alignment="center", font_color=_t.colors.kpi_positive),
        ElementBlueprint(key="kpi_delta_1", x_cm=_PAD + _CARD_W + _CARD_GAP + _CARD_INNER,
                         y_cm=_BODY_TOP + 7.8,
                         w_cm=_CARD_W - 2 * _CARD_INNER, h_cm=1.2,
                         font_size_pt=_t.typography.kpi_delta, bold=True,
                         alignment="center", font_color=_t.colors.kpi_positive),
        ElementBlueprint(key="kpi_delta_2", x_cm=_PAD + 2 * (_CARD_W + _CARD_GAP) + _CARD_INNER,
                         y_cm=_BODY_TOP + 7.8,
                         w_cm=_CARD_W - 2 * _CARD_INNER, h_cm=1.2,
                         font_size_pt=_t.typography.kpi_delta, bold=True,
                         alignment="center", font_color=_t.colors.kpi_positive),
    ],
)

_IMAGE_TEXT_SPLIT = SlideBlueprint(
    slide_type=SlideType.IMAGE_TEXT_SPLIT,
    elements=[
        ElementBlueprint(key="headline", x_cm=_PAD, y_cm=_TOP, w_cm=11.5, h_cm=_HDL_H,
                         font_size_pt=_t.typography.slide_headline, bold=True,
                         font_color=_t.colors.headline),
        ElementBlueprint(key="body_area", x_cm=_PAD, y_cm=_BODY_TOP, w_cm=11.5, h_cm=11.0,
                         font_size_pt=_t.typography.body_small,
                         font_color=_t.colors.body,
                         line_spacing=_t.typography.spacing_generous),
        ElementBlueprint(key="image_area", x_cm=14.0, y_cm=0, w_cm=11.4, h_cm=_SL_H),
    ],
)

_COL_W = _t.spacing.column_width
_COL_GAP = _t.spacing.column_gap

_COMPARISON = SlideBlueprint(
    slide_type=SlideType.COMPARISON,
    elements=[
        _headline(),
        # Left column
        ElementBlueprint(key="col_left_bg", x_cm=_PAD, y_cm=_BODY_TOP,
                         w_cm=_COL_W, h_cm=11.0, is_shape=True,
                         shape_fill=_t.colors.card_bg,
                         corner_radius_cm=_t.spacing.card_corner_radius),
        ElementBlueprint(key="col_left_label", x_cm=_PAD + 0.8, y_cm=_BODY_TOP + 0.6,
                         w_cm=_COL_W - 1.6, h_cm=1.6, font_size_pt=20, bold=True,
                         font_color=_t.colors.headline, alignment="center"),
        ElementBlueprint(key="col_left_body", x_cm=_PAD + 0.8, y_cm=_BODY_TOP + 2.8,
                         w_cm=_COL_W - 1.6, h_cm=7.5,
                         font_size_pt=_t.typography.body_compact,
                         font_color=_t.colors.body,
                         line_spacing=_t.typography.spacing_comparison),
        # Divider — more prominent gap, no thin line
        ElementBlueprint(key="divider", x_cm=_PAD + _COL_W + _COL_GAP / 2 - 0.03,
                         y_cm=_BODY_TOP + 0.5,
                         w_cm=_t.spacing.divider_width, h_cm=10.0, is_shape=True,
                         shape_fill=_t.colors.divider),
        # Right column
        ElementBlueprint(key="col_right_bg", x_cm=_PAD + _COL_W + _COL_GAP, y_cm=_BODY_TOP,
                         w_cm=_COL_W, h_cm=11.0, is_shape=True,
                         shape_fill=_t.colors.card_bg,
                         corner_radius_cm=_t.spacing.card_corner_radius),
        ElementBlueprint(key="col_right_label", x_cm=_PAD + _COL_W + _COL_GAP + 0.8,
                         y_cm=_BODY_TOP + 0.6,
                         w_cm=_COL_W - 1.6, h_cm=1.6, font_size_pt=20, bold=True,
                         font_color=_t.colors.headline, alignment="center"),
        ElementBlueprint(key="col_right_body", x_cm=_PAD + _COL_W + _COL_GAP + 0.8,
                         y_cm=_BODY_TOP + 2.8,
                         w_cm=_COL_W - 1.6, h_cm=7.5,
                         font_size_pt=_t.typography.body_compact,
                         font_color=_t.colors.body,
                         line_spacing=_t.typography.spacing_comparison),
    ],
)

_TIMELINE = SlideBlueprint(
    slide_type=SlideType.TIMELINE,
    elements=[
        _headline(),
        # Timeline track (horizontal line)
        ElementBlueprint(key="track_line", x_cm=_PAD, y_cm=9.5,
                         w_cm=_SL_W - 2 * _PAD,
                         h_cm=_t.spacing.timeline_track_height,
                         is_shape=True, shape_fill=_t.colors.divider),
        # Timeline nodes — dynamically positioned by engine based on entry count
        # These are template positions for up to 5 entries
        ElementBlueprint(key="node_0", x_cm=3.0, y_cm=9.1,
                         w_cm=_t.spacing.timeline_node_size,
                         h_cm=_t.spacing.timeline_node_size,
                         is_shape=True, shape_fill="accent",
                         corner_radius_cm=_t.spacing.timeline_node_radius),
        ElementBlueprint(key="node_1", x_cm=7.5, y_cm=9.1,
                         w_cm=_t.spacing.timeline_node_size,
                         h_cm=_t.spacing.timeline_node_size,
                         is_shape=True, shape_fill="accent",
                         corner_radius_cm=_t.spacing.timeline_node_radius),
        ElementBlueprint(key="node_2", x_cm=12.0, y_cm=9.1,
                         w_cm=_t.spacing.timeline_node_size,
                         h_cm=_t.spacing.timeline_node_size,
                         is_shape=True, shape_fill="accent",
                         corner_radius_cm=_t.spacing.timeline_node_radius),
        ElementBlueprint(key="node_3", x_cm=16.5, y_cm=9.1,
                         w_cm=_t.spacing.timeline_node_size,
                         h_cm=_t.spacing.timeline_node_size,
                         is_shape=True, shape_fill="accent",
                         corner_radius_cm=_t.spacing.timeline_node_radius),
        ElementBlueprint(key="node_4", x_cm=21.0, y_cm=9.1,
                         w_cm=_t.spacing.timeline_node_size,
                         h_cm=_t.spacing.timeline_node_size,
                         is_shape=True, shape_fill="accent",
                         corner_radius_cm=_t.spacing.timeline_node_radius),
        # Date labels (above track)
        ElementBlueprint(key="date_0", x_cm=1.5, y_cm=7.5, w_cm=3.9, h_cm=1.2,
                         font_size_pt=_t.typography.timeline_date,
                         font_color="accent", bold=True, alignment="center"),
        ElementBlueprint(key="date_1", x_cm=6.0, y_cm=7.5, w_cm=3.9, h_cm=1.2,
                         font_size_pt=_t.typography.timeline_date,
                         font_color="accent", bold=True, alignment="center"),
        ElementBlueprint(key="date_2", x_cm=10.5, y_cm=7.5, w_cm=3.9, h_cm=1.2,
                         font_size_pt=_t.typography.timeline_date,
                         font_color="accent", bold=True, alignment="center"),
        ElementBlueprint(key="date_3", x_cm=15.0, y_cm=7.5, w_cm=3.9, h_cm=1.2,
                         font_size_pt=_t.typography.timeline_date,
                         font_color="accent", bold=True, alignment="center"),
        ElementBlueprint(key="date_4", x_cm=19.5, y_cm=7.5, w_cm=3.9, h_cm=1.2,
                         font_size_pt=_t.typography.timeline_date,
                         font_color="accent", bold=True, alignment="center"),
        # Title labels (below track)
        ElementBlueprint(key="entry_title_0", x_cm=1.5, y_cm=10.5, w_cm=3.9, h_cm=1.5,
                         font_size_pt=_t.typography.entry_title, bold=True,
                         alignment="center", font_color=_t.colors.headline),
        ElementBlueprint(key="entry_title_1", x_cm=6.0, y_cm=10.5, w_cm=3.9, h_cm=1.5,
                         font_size_pt=_t.typography.entry_title, bold=True,
                         alignment="center", font_color=_t.colors.headline),
        ElementBlueprint(key="entry_title_2", x_cm=10.5, y_cm=10.5, w_cm=3.9, h_cm=1.5,
                         font_size_pt=_t.typography.entry_title, bold=True,
                         alignment="center", font_color=_t.colors.headline),
        ElementBlueprint(key="entry_title_3", x_cm=15.0, y_cm=10.5, w_cm=3.9, h_cm=1.5,
                         font_size_pt=_t.typography.entry_title, bold=True,
                         alignment="center", font_color=_t.colors.headline),
        ElementBlueprint(key="entry_title_4", x_cm=19.5, y_cm=10.5, w_cm=3.9, h_cm=1.5,
                         font_size_pt=_t.typography.entry_title, bold=True,
                         alignment="center", font_color=_t.colors.headline),
        # Description labels
        ElementBlueprint(key="entry_desc_0", x_cm=1.5, y_cm=12.0, w_cm=3.9, h_cm=3.0,
                         font_size_pt=_t.typography.body_timeline_desc,
                         font_color=_t.colors.muted, alignment="center"),
        ElementBlueprint(key="entry_desc_1", x_cm=6.0, y_cm=12.0, w_cm=3.9, h_cm=3.0,
                         font_size_pt=_t.typography.body_timeline_desc,
                         font_color=_t.colors.muted, alignment="center"),
        ElementBlueprint(key="entry_desc_2", x_cm=10.5, y_cm=12.0, w_cm=3.9, h_cm=3.0,
                         font_size_pt=_t.typography.body_timeline_desc,
                         font_color=_t.colors.muted, alignment="center"),
        ElementBlueprint(key="entry_desc_3", x_cm=15.0, y_cm=12.0, w_cm=3.9, h_cm=3.0,
                         font_size_pt=_t.typography.body_timeline_desc,
                         font_color=_t.colors.muted, alignment="center"),
        ElementBlueprint(key="entry_desc_4", x_cm=19.5, y_cm=12.0, w_cm=3.9, h_cm=3.0,
                         font_size_pt=_t.typography.body_timeline_desc,
                         font_color=_t.colors.muted, alignment="center"),
    ],
)

_PROCESS_FLOW = SlideBlueprint(
    slide_type=SlideType.PROCESS_FLOW,
    elements=[
        _headline(),
        # Process steps — dynamically positioned. Template for 4 steps:
        ElementBlueprint(key="step_box_0", x_cm=_PAD, y_cm=_BODY_TOP + 0.5,
                         w_cm=_t.spacing.step_box_width, h_cm=10.5, is_shape=True,
                         shape_fill=_t.colors.process_step_bg, corner_radius_cm=0.3),
        ElementBlueprint(key="step_box_1", x_cm=_PAD + 5.5, y_cm=_BODY_TOP + 0.5,
                         w_cm=_t.spacing.step_box_width, h_cm=10.5, is_shape=True,
                         shape_fill=_t.colors.process_step_bg, corner_radius_cm=0.3),
        ElementBlueprint(key="step_box_2", x_cm=_PAD + 11.0, y_cm=_BODY_TOP + 0.5,
                         w_cm=_t.spacing.step_box_width, h_cm=10.5, is_shape=True,
                         shape_fill=_t.colors.process_step_bg, corner_radius_cm=0.3),
        ElementBlueprint(key="step_box_3", x_cm=_PAD + 16.5, y_cm=_BODY_TOP + 0.5,
                         w_cm=_t.spacing.step_box_width, h_cm=10.5, is_shape=True,
                         shape_fill=_t.colors.process_step_bg, corner_radius_cm=0.3),
        # Step numbers (circles)
        ElementBlueprint(key="step_num_0", x_cm=_PAD + 1.6, y_cm=_BODY_TOP + 1.2,
                         w_cm=_t.spacing.step_number_size,
                         h_cm=_t.spacing.step_number_size,
                         is_shape=True, shape_fill="accent",
                         corner_radius_cm=_t.spacing.step_number_radius,
                         font_size_pt=_t.typography.step_number,
                         font_color=_t.colors.text_on_dark,
                         bold=True, alignment="center"),
        ElementBlueprint(key="step_num_1", x_cm=_PAD + 7.1, y_cm=_BODY_TOP + 1.2,
                         w_cm=_t.spacing.step_number_size,
                         h_cm=_t.spacing.step_number_size,
                         is_shape=True, shape_fill="accent",
                         corner_radius_cm=_t.spacing.step_number_radius,
                         font_size_pt=_t.typography.step_number,
                         font_color=_t.colors.text_on_dark,
                         bold=True, alignment="center"),
        ElementBlueprint(key="step_num_2", x_cm=_PAD + 12.6, y_cm=_BODY_TOP + 1.2,
                         w_cm=_t.spacing.step_number_size,
                         h_cm=_t.spacing.step_number_size,
                         is_shape=True, shape_fill="accent",
                         corner_radius_cm=_t.spacing.step_number_radius,
                         font_size_pt=_t.typography.step_number,
                         font_color=_t.colors.text_on_dark,
                         bold=True, alignment="center"),
        ElementBlueprint(key="step_num_3", x_cm=_PAD + 18.1, y_cm=_BODY_TOP + 1.2,
                         w_cm=_t.spacing.step_number_size,
                         h_cm=_t.spacing.step_number_size,
                         is_shape=True, shape_fill="accent",
                         corner_radius_cm=_t.spacing.step_number_radius,
                         font_size_pt=_t.typography.step_number,
                         font_color=_t.colors.text_on_dark,
                         bold=True, alignment="center"),
        # Step titles
        ElementBlueprint(key="step_title_0", x_cm=_PAD + 0.4, y_cm=_BODY_TOP + 3.5,
                         w_cm=4.0, h_cm=1.5,
                         font_size_pt=_t.typography.step_title, bold=True,
                         alignment="center", font_color=_t.colors.headline),
        ElementBlueprint(key="step_title_1", x_cm=_PAD + 5.9, y_cm=_BODY_TOP + 3.5,
                         w_cm=4.0, h_cm=1.5,
                         font_size_pt=_t.typography.step_title, bold=True,
                         alignment="center", font_color=_t.colors.headline),
        ElementBlueprint(key="step_title_2", x_cm=_PAD + 11.4, y_cm=_BODY_TOP + 3.5,
                         w_cm=4.0, h_cm=1.5,
                         font_size_pt=_t.typography.step_title, bold=True,
                         alignment="center", font_color=_t.colors.headline),
        ElementBlueprint(key="step_title_3", x_cm=_PAD + 16.9, y_cm=_BODY_TOP + 3.5,
                         w_cm=4.0, h_cm=1.5,
                         font_size_pt=_t.typography.step_title, bold=True,
                         alignment="center", font_color=_t.colors.headline),
        # Step descriptions
        ElementBlueprint(key="step_desc_0", x_cm=_PAD + 0.4, y_cm=_BODY_TOP + 5.2,
                         w_cm=4.0, h_cm=5.0,
                         font_size_pt=_t.typography.body_description,
                         font_color=_t.colors.body, alignment="center",
                         line_spacing=_t.typography.spacing_default),
        ElementBlueprint(key="step_desc_1", x_cm=_PAD + 5.9, y_cm=_BODY_TOP + 5.2,
                         w_cm=4.0, h_cm=5.0,
                         font_size_pt=_t.typography.body_description,
                         font_color=_t.colors.body, alignment="center",
                         line_spacing=_t.typography.spacing_default),
        ElementBlueprint(key="step_desc_2", x_cm=_PAD + 11.4, y_cm=_BODY_TOP + 5.2,
                         w_cm=4.0, h_cm=5.0,
                         font_size_pt=_t.typography.body_description,
                         font_color=_t.colors.body, alignment="center",
                         line_spacing=_t.typography.spacing_default),
        ElementBlueprint(key="step_desc_3", x_cm=_PAD + 16.9, y_cm=_BODY_TOP + 5.2,
                         w_cm=4.0, h_cm=5.0,
                         font_size_pt=_t.typography.body_description,
                         font_color=_t.colors.body, alignment="center",
                         line_spacing=_t.typography.spacing_default),
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
                         w_cm=5.5, h_cm=12.0,
                         font_size_pt=_t.typography.chart_takeaway,
                         font_color=_t.colors.muted,
                         line_spacing=_t.typography.spacing_relaxed),
    ],
)

_IMAGE_FULLBLEED = SlideBlueprint(
    slide_type=SlideType.IMAGE_FULLBLEED,
    elements=[
        ElementBlueprint(key="background_image", x_cm=0, y_cm=0,
                         w_cm=_SL_W, h_cm=_SL_H),
        ElementBlueprint(key="overlay_bg", x_cm=0, y_cm=13.0,
                         w_cm=_SL_W, h_cm=6.05, is_shape=True,
                         shape_fill=_t.colors.overlay),  # 50% opacity applied in renderer
        ElementBlueprint(key="headline", x_cm=_PAD, y_cm=13.8,
                         w_cm=_SL_W - 2 * _PAD, h_cm=3.5,
                         font_size_pt=_t.typography.fullbleed_headline, bold=True,
                         font_color=_t.colors.text_on_dark),
    ],
)

_AGENDA = SlideBlueprint(
    slide_type=SlideType.AGENDA,
    elements=[
        _headline(size=_t.typography.agenda_headline),
        ElementBlueprint(key="agenda_list", x_cm=_PAD, y_cm=_BODY_TOP + 0.5,
                         w_cm=15.0, h_cm=12.0, font_size_pt=20,
                         font_color=_t.colors.body,
                         line_spacing=_t.typography.spacing_list),
    ],
)

_CLOSING = SlideBlueprint(
    slide_type=SlideType.CLOSING,
    elements=[
        ElementBlueprint(key="headline", x_cm=_PAD, y_cm=4.0,
                         w_cm=_SL_W - 2 * _PAD, h_cm=3.5,
                         font_size_pt=_t.typography.closing_title, bold=True,
                         alignment="center", font_color=_t.colors.headline),
        ElementBlueprint(key="takeaways", x_cm=4.5, y_cm=8.5,
                         w_cm=16.4, h_cm=5.5, font_size_pt=17,
                         alignment="center", font_color=_t.colors.body,
                         line_spacing=_t.typography.spacing_closing),
        ElementBlueprint(key="contact", x_cm=4.5, y_cm=15.5,
                         w_cm=16.4, h_cm=2.0,
                         font_size_pt=_t.typography.contact,
                         alignment="center", font_color=_t.colors.subtle),
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
