"""Shared PresentationSpec Domain Model.

This is the contract between the Python pipeline (content intelligence)
and the TypeScript render-service (visual rendering). Both sides must
understand and validate this schema.

The Python side produces a PresentationSpec after stages 1-5.
The TS render-service consumes it and produces PPTX output.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ── Enums ─────────────────────────────────────────────────────────────────────

class RenderMode(str, Enum):
    """How this presentation should be rendered."""
    DESIGN = "design"       # AI-designed, HTML-first, visual excellence
    TEMPLATE = "template"   # Corporate template, deterministic placement


class SlideIntent(str, Enum):
    """Semantic purpose of a slide — determines layout family."""
    HERO = "hero"                 # Title/opening slide
    SECTION = "section"           # Section divider
    STATEMENT = "statement"       # Key message / quote
    CONTENT_BULLETS = "bullets"   # Focused bullet points
    CONTENT_CARDS = "cards"       # 3-column card grid
    CONTENT_KPI = "kpi"           # KPI dashboard
    CONTENT_SPLIT = "split"       # Image + text split
    CONTENT_COMPARE = "compare"   # Side-by-side comparison
    CONTENT_TIMELINE = "timeline" # Chronological progression
    CONTENT_PROCESS = "process"   # Step-by-step flow
    CONTENT_CHART = "chart"       # Data visualization
    VISUAL_HERO = "visual_hero"   # Full-bleed image
    AGENDA = "agenda"             # Agenda/overview
    CLOSING = "closing"           # Summary/closing


class VisualAssetType(str, Enum):
    """Type of visual asset on a slide."""
    NONE = "none"
    PHOTO = "photo"
    ILLUSTRATION = "illustration"
    ICON = "icon"
    CHART = "chart"
    DIAGRAM = "diagram"


class VisualAssetRole(str, Enum):
    """Functional role of the visual asset."""
    NONE = "none"
    HERO = "hero"           # Primary visual, carries the slide
    SUPPORTING = "supporting"  # Enhances text content
    EVIDENCE = "evidence"      # Data/proof supporting the claim


class ChartType(str, Enum):
    BAR = "bar"
    LINE = "line"
    PIE = "pie"
    DONUT = "donut"
    STACKED_BAR = "stacked_bar"
    HORIZONTAL_BAR = "horizontal_bar"


class ContentBlockType(str, Enum):
    TEXT = "text"
    BULLETS = "bullets"
    CARD = "card"
    KPI = "kpi"
    QUOTE = "quote"
    COMPARISON_COLUMN = "comparison_column"
    TIMELINE_ENTRY = "timeline_entry"
    PROCESS_STEP = "process_step"


# ── Content Blocks ────────────────────────────────────────────────────────────

class BulletItem(BaseModel):
    bold_prefix: str = ""
    text: str


class ContentBlock(BaseModel):
    """Union-typed content block. The `block_type` determines which fields are used."""
    block_type: ContentBlockType

    # text
    text: str = ""

    # bullets
    items: list[BulletItem] = Field(default_factory=list)

    # card
    title: str = ""
    body: str = ""
    icon_emoji: str = ""  # Resolved emoji, NOT raw icon_hint

    # kpi
    label: str = ""
    value: str = ""
    trend: str = ""  # up, down, neutral
    delta: str = ""

    # quote
    attribution: str = ""

    # comparison_column
    column_label: str = ""
    column_items: list[str] = Field(default_factory=list)

    # timeline_entry
    date: str = ""
    description: str = ""

    # process_step
    step_number: int = 0


# ── Visual Asset ──────────────────────────────────────────────────────────────

class ChartSpec(BaseModel):
    """Chart specification for data visualization slides."""
    chart_type: ChartType
    title: str = ""
    labels: list[str] = Field(default_factory=list)
    datasets: list[dict] = Field(default_factory=list)


class VisualAsset(BaseModel):
    """Visual asset specification — image or chart."""
    asset_type: VisualAssetType = VisualAssetType.NONE
    role: VisualAssetRole = VisualAssetRole.NONE
    # For images: generation prompt (internal, never shown on slide)
    generation_prompt: str = ""
    # For images: pre-generated image path or URL
    image_url: str = ""
    # For charts
    chart_spec: Optional[ChartSpec] = None


# ── Slide Spec ────────────────────────────────────────────────────────────────

class SlideSpec(BaseModel):
    """Complete specification for one slide.

    This is the atomic unit exchanged between pipeline and renderer.
    All text content is FINAL — no placeholders, no descriptors, no metadata.
    """
    position: int
    intent: SlideIntent
    render_mode: RenderMode = RenderMode.DESIGN

    # Text content (all final, validated, no leaks)
    headline: str = ""
    subheadline: str = ""
    core_message: str = ""  # Internal — not rendered, used for speaker notes
    speaker_notes: str = ""

    # Structured content
    content_blocks: list[ContentBlock] = Field(default_factory=list)

    # Visual
    visual: VisualAsset = Field(default_factory=VisualAsset)

    # Design hints (for renderer, not content)
    transition_hint: str = ""


# ── Quality Score ─────────────────────────────────────────────────────────────

class QualityDimension(BaseModel):
    """Score for one quality dimension."""
    name: str
    score: float  # 0-100
    details: str = ""


class QualityScore(BaseModel):
    """Quality assessment for a slide or deck."""
    total: float = 0.0  # 0-100
    passed: bool = False
    dimensions: list[QualityDimension] = Field(default_factory=list)


# ── Template Descriptor ──────────────────────────────────────────────────────

class PlaceholderSlot(BaseModel):
    """A placeholder in a template layout that can be filled."""
    slot_id: str
    slot_type: str  # title, body, image, chart, footer
    x_cm: float = 0
    y_cm: float = 0
    width_cm: float = 0
    height_cm: float = 0


class TemplateLayout(BaseModel):
    """A layout within a template."""
    layout_index: int
    layout_name: str
    supported_intents: list[SlideIntent] = Field(default_factory=list)
    placeholders: list[PlaceholderSlot] = Field(default_factory=list)


class TemplateDescriptor(BaseModel):
    """Complete description of an uploaded template."""
    template_id: str
    filename: str
    layouts: list[TemplateLayout] = Field(default_factory=list)
    color_scheme: dict[str, str] = Field(default_factory=dict)
    font_scheme: dict[str, str] = Field(default_factory=dict)


# ── Presentation Spec (top-level) ─────────────────────────────────────────────

class PresentationSpec(BaseModel):
    """The complete, validated specification for a presentation.

    This is the contract between content intelligence (Python) and
    rendering (TypeScript). Everything in this spec is FINAL:
    - No placeholder text
    - No raw descriptors
    - No unresolved icon hints
    - All content validated against quality rules
    - Visual assets resolved (generated images have URLs, charts have data)

    The render-service takes this and produces a .pptx file without
    making any content decisions.
    """
    # Metadata
    title: str = ""
    render_mode: RenderMode = RenderMode.DESIGN
    template_id: Optional[str] = None

    # Design parameters
    accent_color: str = "#2563EB"
    font_family: str = "Calibri"

    # Content
    slides: list[SlideSpec] = Field(default_factory=list)

    # Quality
    quality: QualityScore = Field(default_factory=QualityScore)

    # Template (only for template mode)
    template: Optional[TemplateDescriptor] = None
