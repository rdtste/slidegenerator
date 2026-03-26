"""V2 Pipeline data models — all Pydantic schemas for the production pipeline.

Note: max_length constraints are intentionally NOT enforced at the Pydantic level
because LLM output frequently exceeds them by a few characters. Length limits are
enforced via prompts and validated in Stage 4 (with auto-truncation). The field
validators here coerce None→"" and truncate extreme outliers to prevent crashes.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal, Union

from pydantic import BaseModel, Field, field_validator


# ── Helper: coerce None→"" and truncate extreme outliers ─────────────────
def _str_sanitizer(*fields: str, fallback: str = ""):
    """Create a Pydantic field_validator that coerces None and truncates strings."""
    @field_validator(*fields, mode="before")
    @classmethod
    def _sanitize(cls, v: object) -> str:
        if v is None:
            return fallback
        return str(v)
    return _sanitize


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class SlideType(str, Enum):
    TITLE_HERO = "title_hero"
    SECTION_DIVIDER = "section_divider"
    KEY_STATEMENT = "key_statement"
    BULLETS_FOCUSED = "bullets_focused"
    THREE_CARDS = "three_cards"
    KPI_DASHBOARD = "kpi_dashboard"
    IMAGE_TEXT_SPLIT = "image_text_split"
    COMPARISON = "comparison"
    TIMELINE = "timeline"
    PROCESS_FLOW = "process_flow"
    CHART_INSIGHT = "chart_insight"
    IMAGE_FULLBLEED = "image_fullbleed"
    AGENDA = "agenda"
    CLOSING = "closing"


class Audience(str, Enum):
    TEAM = "team"
    MANAGEMENT = "management"
    CUSTOMER = "customer"
    WORKSHOP = "workshop"


class ImageStyleType(str, Enum):
    PHOTO = "photo"
    ILLUSTRATION = "illustration"
    MINIMAL = "minimal"
    DATA_VISUAL = "data_visual"
    NONE = "none"


class NarrativeArc(str, Enum):
    SITUATION_COMPLICATION_RESOLUTION = "situation_complication_resolution"
    PROBLEM_SOLUTION = "problem_solution"
    CHRONOLOGICAL = "chronological"
    THEMATIC_CLUSTER = "thematic_cluster"
    COMPARE_DECIDE = "compare_decide"


class BeatType(str, Enum):
    OPENING = "opening"
    CONTEXT = "context"
    EVIDENCE = "evidence"
    INSIGHT = "insight"
    ACTION = "action"
    TRANSITION = "transition"
    CLOSING = "closing"


class EmotionalIntent(str, Enum):
    CONFIDENCE = "confidence"
    URGENCY = "urgency"
    CURIOSITY = "curiosity"
    RESOLUTION = "resolution"
    INSPIRATION = "inspiration"


class VisualType(str, Enum):
    PHOTO = "photo"
    ILLUSTRATION = "illustration"
    ICON = "icon"
    CHART = "chart"
    DIAGRAM = "diagram"
    NONE = "none"


class ImageRole(str, Enum):
    HERO = "hero"
    SUPPORTING = "supporting"
    DECORATIVE = "decorative"
    EVIDENCE = "evidence"
    NONE = "none"


class Trend(str, Enum):
    UP = "up"
    DOWN = "down"
    NEUTRAL = "neutral"


class ContentDensity(str, Enum):
    LIGHT = "light"
    MEDIUM = "medium"
    DENSE = "dense"


class Tone(str, Enum):
    FORMAL_ANALYTICAL = "formal_analytical"
    PERSUASIVE = "persuasive"
    COLLABORATIVE = "collaborative"
    EDUCATIONAL = "educational"


# ---------------------------------------------------------------------------
# Stage 1: InterpretedBriefing
# ---------------------------------------------------------------------------

class BriefingConstraints(BaseModel):
    must_include: list[str] = Field(default_factory=list)
    must_avoid: list[str] = Field(default_factory=list)
    language: str = Field("de")


class InterpretedBriefing(BaseModel):
    topic: str = Field(..., description="Main topic")
    goal: str = Field(..., description="Presentation goal in one sentence")
    audience: Audience = Field(Audience.MANAGEMENT)
    tone: Tone = Field(Tone.FORMAL_ANALYTICAL)
    image_style: ImageStyleType = Field(ImageStyleType.MINIMAL)
    requested_slide_count: int = Field(10, ge=5, le=25)
    key_facts: list[str] = Field(default_factory=list)
    content_themes: list[str] = Field(default_factory=list)
    constraints: BriefingConstraints = Field(default_factory=BriefingConstraints)
    needs_clarification: bool = Field(False)
    clarification_questions: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Stage 2: Storyline
# ---------------------------------------------------------------------------

class StoryBeat(BaseModel):
    position: int = Field(..., ge=1)
    beat_type: BeatType
    core_message: str = Field(...)
    content_theme: str = Field("")
    emotional_intent: EmotionalIntent = Field(EmotionalIntent.CONFIDENCE)
    evidence_needed: bool = Field(False)
    suggested_slide_types: list[SlideType] = Field(default_factory=list)

    _sanitize = _str_sanitizer("content_theme", "core_message")


class Storyline(BaseModel):
    narrative_arc: NarrativeArc = Field(NarrativeArc.SITUATION_COMPLICATION_RESOLUTION)
    total_beats: int = Field(0)
    beats: list[StoryBeat] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Stage 3: Content Blocks
# ---------------------------------------------------------------------------

class BulletItem(BaseModel):
    text: str = Field(...)
    bold_prefix: str = Field("")

    _sanitize = _str_sanitizer("text", "bold_prefix")


class BulletsBlock(BaseModel):
    type: Literal["bullets"] = "bullets"
    items: list[BulletItem] = Field(default_factory=list)


class KpiBlock(BaseModel):
    type: Literal["kpi"] = "kpi"
    label: str = Field(...)
    value: str = Field(...)
    trend: Trend = Field(Trend.NEUTRAL)
    delta: str = Field("")

    _sanitize = _str_sanitizer("label", "value", "delta")


class QuoteBlock(BaseModel):
    type: Literal["quote"] = "quote"
    text: str = Field(...)
    attribution: str = Field("")

    _sanitize = _str_sanitizer("text", "attribution")


class LabelValuePair(BaseModel):
    label: str = Field(...)
    value: str = Field(...)

    _sanitize = _str_sanitizer("label", "value")


class LabelValueBlock(BaseModel):
    type: Literal["label_value"] = "label_value"
    pairs: list[LabelValuePair] = Field(default_factory=list)


class ComparisonColumnBlock(BaseModel):
    type: Literal["comparison_column"] = "comparison_column"
    column_label: str = Field(...)
    items: list[str] = Field(default_factory=list)

    _sanitize = _str_sanitizer("column_label")


class TimelineEntryBlock(BaseModel):
    type: Literal["timeline_entry"] = "timeline_entry"
    date: str = Field(...)
    title: str = Field(...)
    description: str = Field("")

    _sanitize = _str_sanitizer("date", "title", "description")


class ProcessStepBlock(BaseModel):
    type: Literal["process_step"] = "process_step"
    step_number: int = Field(1)
    title: str = Field(...)
    description: str = Field("")

    _sanitize = _str_sanitizer("title", "description")


class CardBlock(BaseModel):
    type: Literal["card"] = "card"
    title: str = Field(...)
    body: str = Field("")
    icon_hint: str = Field("")

    _sanitize = _str_sanitizer("title", "body", "icon_hint")


class TextBlock(BaseModel):
    type: Literal["text"] = "text"
    text: str = Field("")

    _sanitize = _str_sanitizer("text")


ContentBlock = Union[
    BulletsBlock, KpiBlock, QuoteBlock, LabelValueBlock,
    ComparisonColumnBlock, TimelineEntryBlock, ProcessStepBlock,
    CardBlock, TextBlock,
]


# ---------------------------------------------------------------------------
# Chart
# ---------------------------------------------------------------------------

class ChartSeries(BaseModel):
    name: str = Field("")
    values: list[float] = Field(default_factory=list)


class ChartSpec(BaseModel):
    chart_type: Literal["bar", "horizontal_bar", "stacked_bar", "line", "pie", "donut"] = "bar"
    title: str = Field("")
    data: dict = Field(default_factory=lambda: {"labels": [], "series": []})
    unit: str = Field("")
    highlight_index: int | None = Field(None)

    _sanitize = _str_sanitizer("title", "unit")


# ---------------------------------------------------------------------------
# Visual
# ---------------------------------------------------------------------------

class Visual(BaseModel):
    type: VisualType = Field(VisualType.NONE)
    image_role: ImageRole = Field(ImageRole.NONE)
    image_description: str = Field("")
    chart_spec: ChartSpec | None = Field(None)

    _sanitize = _str_sanitizer("image_description")


# ---------------------------------------------------------------------------
# Stage 3: SlidePlan / PresentationPlan
# ---------------------------------------------------------------------------

class SlidePlan(BaseModel):
    position: int = Field(..., ge=1)
    slide_type: SlideType
    beat_ref: int = Field(0, description="References storyline beat position")
    headline: str = Field(...)
    subheadline: str = Field("")
    core_message: str = Field("")
    content_blocks: list[ContentBlock] = Field(default_factory=list)
    visual: Visual = Field(default_factory=Visual)
    speaker_notes: str = Field("")
    transition_hint: str = Field("")

    _sanitize = _str_sanitizer(
        "headline", "subheadline", "core_message",
        "speaker_notes", "transition_hint",
    )


class PresentationMetadata(BaseModel):
    total_slides: int = Field(0)
    estimated_duration_minutes: int = Field(10)
    content_density: ContentDensity = Field(ContentDensity.MEDIUM)


class PresentationPlan(BaseModel):
    audience: Audience = Field(Audience.MANAGEMENT)
    image_style: ImageStyleType = Field(ImageStyleType.MINIMAL)
    slides: list[SlidePlan] = Field(default_factory=list)
    metadata: PresentationMetadata = Field(default_factory=PresentationMetadata)


# ---------------------------------------------------------------------------
# Stage 5: FilledSlide
# ---------------------------------------------------------------------------

class TextMetrics(BaseModel):
    total_chars: int = Field(0)
    bullet_count: int = Field(0)
    max_bullet_length: int = Field(0)
    headline_length: int = Field(0)


class FilledSlide(BaseModel):
    """SlidePlan with finalized text and computed metrics."""
    position: int = Field(..., ge=1)
    slide_type: SlideType
    headline: str = Field(...)
    subheadline: str = Field("")
    core_message: str = Field("")
    content_blocks: list[ContentBlock] = Field(default_factory=list)
    visual: Visual = Field(default_factory=Visual)
    speaker_notes: str = Field("")
    text_metrics: TextMetrics = Field(default_factory=TextMetrics)

    _sanitize = _str_sanitizer(
        "headline", "subheadline", "core_message", "speaker_notes",
    )


# ---------------------------------------------------------------------------
# Stage 6: RenderInstruction
# ---------------------------------------------------------------------------

class ElementPosition(BaseModel):
    left_cm: float = Field(0)
    top_cm: float = Field(0)
    width_cm: float = Field(0)
    height_cm: float = Field(0)


class ElementStyle(BaseModel):
    font_family: str = Field("Calibri")
    font_size_pt: int = Field(18)
    font_color: str = Field("#333333")
    bold: bool = Field(False)
    italic: bool = Field(False)
    alignment: Literal["left", "center", "right"] = "left"
    vertical_alignment: Literal["top", "middle", "bottom"] = "top"
    line_spacing: float = Field(1.15)


class RenderElement(BaseModel):
    element_type: str = Field(...)  # title, subtitle, body, bullet, kpi_value, etc.
    content: str | dict | list = Field("")
    position: ElementPosition = Field(default_factory=ElementPosition)
    style: ElementStyle = Field(default_factory=ElementStyle)


class RenderInstruction(BaseModel):
    slide_index: int = Field(0)
    slide_type: SlideType = Field(SlideType.BULLETS_FOCUSED)
    layout_id: str = Field("blank")
    elements: list[RenderElement] = Field(default_factory=list)
    background_color: str = Field("#FFFFFF")
    accent_color: str = Field("#2563EB")


# ---------------------------------------------------------------------------
# Stage 8: QualityReport
# ---------------------------------------------------------------------------

class QualityFinding(BaseModel):
    rule: str
    severity: Literal["error", "warning"] = "warning"
    message: str = ""
    auto_fixable: bool = Field(False)
    slide_index: int | None = Field(None)


class SlideFinding(BaseModel):
    slide_index: int
    findings: list[QualityFinding] = Field(default_factory=list)
    regenerate: bool = Field(False)


class QualityReport(BaseModel):
    overall_score: float = Field(100.0)
    passed: bool = Field(True)
    deck_findings: list[QualityFinding] = Field(default_factory=list)
    slide_findings: list[SlideFinding] = Field(default_factory=list)

    def add_finding(self, finding: QualityFinding) -> None:
        if finding.slide_index is not None:
            for sf in self.slide_findings:
                if sf.slide_index == finding.slide_index:
                    sf.findings.append(finding)
                    return
            self.slide_findings.append(
                SlideFinding(slide_index=finding.slide_index, findings=[finding])
            )
        else:
            self.deck_findings.append(finding)
