"""Centralized Design Token System.

All hardcoded design values (colors, spacing, typography) extracted from blueprints
and renderers into a single source of truth. Blueprints and engines reference tokens
instead of magic numbers.
"""

from __future__ import annotations

from dataclasses import dataclass, field


# ── Color Palette ──────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ColorPalette:
    """Semantic color tokens for slide rendering."""

    # Text hierarchy
    headline: str = "#1a1a2e"
    body: str = "#374151"
    muted: str = "#6b7280"
    subtle: str = "#9ca3af"

    # Surfaces
    card_bg: str = "#f3f4f6"
    process_step_bg: str = "#eef2ff"
    slide_bg: str = "#FFFFFF"

    # Structural elements
    divider: str = "#d1d5db"
    overlay: str = "#000000"

    # Data visualization
    kpi_positive: str = "#22c55e"
    kpi_negative: str = "#ef4444"
    kpi_neutral: str = "#6b7280"

    # Inverse (dark backgrounds)
    text_on_dark: str = "#FFFFFF"
    text_on_dark_muted: str = "#d1d5db"
    quote_mark: str = "#e5e7eb"


# ── Spacing Tokens ─────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class SpacingTokens:
    """Spatial tokens in cm for the 33.867 x 19.05 cm slide canvas (16:9 widescreen)."""

    # Canvas (16:9 = 13.333" x 7.5" = 33.867 x 19.05 cm)
    slide_width: float = 33.867
    slide_height: float = 19.05

    # Margins & padding
    side_padding: float = 2.2
    top_padding: float = 1.8
    content_gap: float = 0.8

    # Headline zone
    headline_height: float = 2.2
    body_top: float = 5.2       # where body content begins (after headline + whitespace)

    # Card system (3 cards: 3*9.0 + 2*1.2 = 29.4 ≈ content_width 29.467)
    card_width: float = 9.0
    card_gap: float = 1.2
    card_inner_padding: float = 0.8
    card_corner_radius: float = 0.4

    # Comparison columns (2 cols: 2*14.0 + 1.5 = 29.5 ≈ content_width)
    column_width: float = 14.0
    column_gap: float = 1.5

    # Process steps (4 steps: 4*6.7 + 3*0.9 = 29.5 ≈ content_width)
    step_box_width: float = 6.7
    step_box_gap: float = 0.9
    step_number_size: float = 1.6
    step_number_radius: float = 0.8

    # Timeline
    timeline_node_size: float = 0.9
    timeline_node_radius: float = 0.45
    timeline_track_height: float = 0.1

    # Shapes
    accent_bar_height: float = 0.18
    divider_width: float = 0.06

    @property
    def content_width(self) -> float:
        """Usable content width after side padding."""
        return self.slide_width - 2 * self.side_padding


# ── Typography Tokens ──────────────────────────────────────────────────────────

@dataclass(frozen=True)
class TypographyTokens:
    """Font size tokens in pt and line spacing multipliers."""

    # Headlines
    hero_title: int = 44
    section_title: int = 40
    closing_title: int = 34
    slide_headline: int = 28
    agenda_headline: int = 32
    fullbleed_headline: int = 32
    statement_text: int = 32

    # Body text
    body_default: int = 18
    body_small: int = 16
    body_compact: int = 15
    body_card: int = 13
    body_description: int = 12
    body_timeline_desc: int = 11

    # Labels & metadata
    subheadline: int = 22
    subheadline_small: int = 18
    card_title: int = 17
    step_title: int = 16
    entry_title: int = 14
    chart_takeaway: int = 14
    kpi_label: int = 13
    contact: int = 13
    timeline_date: int = 12
    attribution: int = 16
    step_number: int = 20

    # KPI values (hero element)
    kpi_value: int = 44
    kpi_delta: int = 16

    # Decorative
    quote_mark: int = 120
    card_icon: int = 36

    # Line spacing
    spacing_tight: float = 1.15
    spacing_default: float = 1.3
    spacing_relaxed: float = 1.4
    spacing_generous: float = 1.5
    spacing_statement: float = 1.4
    spacing_bullets: float = 1.8
    spacing_list: float = 2.0
    spacing_closing: float = 1.8
    spacing_comparison: float = 1.6


# ── Composition Constraints ───────────────────────────────────────────────────

@dataclass(frozen=True)
class CompositionConstraints:
    """Quantitative limits that enforce visual quality."""

    # Text density: max characters per slide type
    # (Duplicated from slide_rules for single-source access)
    max_headline_chars: int = 70
    max_bullet_chars: int = 60

    # Content area ratios (content_area / total_slide_area)
    max_content_coverage: float = 0.65   # never fill more than 65% of slide
    min_whitespace_ratio: float = 0.35   # at least 35% whitespace

    # Card/KPI balance: max deviation between shortest and longest card body
    max_card_length_deviation: float = 2.0  # ratio of longest/shortest

    # Visual-to-text ratio: slides with visuals should have less text
    visual_slide_text_reduction: float = 0.7  # 30% less text when image present

    # Content density: chars per cm² of available content area
    max_chars_per_cm2: float = 2.5

    # Preflight thresholds
    preflight_pass_score: int = 70
    preflight_warn_score: int = 50


# ── Default Token Set ──────────────────────────────────────────────────────────

@dataclass(frozen=True)
class DesignTokens:
    """Complete design token set — the single source of truth for all design values."""

    colors: ColorPalette = field(default_factory=ColorPalette)
    spacing: SpacingTokens = field(default_factory=SpacingTokens)
    typography: TypographyTokens = field(default_factory=TypographyTokens)
    composition: CompositionConstraints = field(default_factory=CompositionConstraints)


# Singleton default tokens
DEFAULT_TOKENS = DesignTokens()
