"""Unified content model — bridge between V1 and V2 data structures.

This module defines a template-agnostic presentation specification
that both Design Mode and Template Mode can produce and consume.

It does NOT replace the existing V1 (PresentationData/SlideContent) or
V2 (PresentationPlan/SlidePlan/FilledSlide) models. Instead, it provides
converters so both pipelines can feed into a common rendering interface.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class SlideLayout(str, Enum):
    """Semantic slide layout types — shared between both modes."""

    TITLE = "title"
    SECTION = "section"
    CONTENT = "content"
    TWO_COLUMN = "two_column"
    IMAGE = "image"
    CHART = "chart"
    CLOSING = "closing"
    # Extended types from V2 (Design Mode only)
    KEY_STATEMENT = "key_statement"
    THREE_CARDS = "three_cards"
    KPI_DASHBOARD = "kpi_dashboard"
    TIMELINE = "timeline"
    PROCESS_FLOW = "process_flow"
    AGENDA = "agenda"
    IMAGE_FULLBLEED = "image_fullbleed"
    COMPARISON = "comparison"


class SlideSpec(BaseModel):
    """Template-agnostic specification for a single slide.

    This is the common currency between planning and rendering.
    Both V1 and V2 pipelines produce SlideSpecs via converters.
    """

    position: int = Field(1, ge=1)
    layout: SlideLayout = Field(SlideLayout.CONTENT)
    title: str = Field("")
    subtitle: str = Field("")
    body: str = Field("")
    bullets: list[str] = Field(default_factory=list)
    speaker_notes: str = Field("")
    image_description: str = Field("")
    chart_data: dict | None = Field(None)
    content_blocks: list[Any] = Field(
        default_factory=list,
        description="V2-style ContentBlock objects for rich content",
    )
    visual: dict | None = Field(None, description="V2-style Visual spec")
    left_column: str = Field("", description="V1 two-column left content")
    right_column: str = Field("", description="V1 two-column right content")
    # Metadata
    core_message: str = Field("")
    headline: str = Field("")
    subheadline: str = Field("")


class PresentationSpec(BaseModel):
    """Template-agnostic specification for a complete presentation."""

    title: str = Field("Presentation")
    author: str = Field("")
    slides: list[SlideSpec] = Field(default_factory=list)
    audience: str = Field("management")
    image_style: str = Field("minimal")


# ---------------------------------------------------------------------------
# Converters
# ---------------------------------------------------------------------------

def from_v1_presentation(data: Any) -> PresentationSpec:
    """Convert V1 PresentationData to PresentationSpec.

    V1 model: app.models.schemas.PresentationData with SlideContent items.
    """
    slides = []
    for i, slide in enumerate(data.slides):
        spec = SlideSpec(
            position=i + 1,
            layout=SlideLayout(slide.layout) if slide.layout in SlideLayout.__members__.values() else SlideLayout.CONTENT,
            title=slide.title or "",
            subtitle=getattr(slide, "subtitle", "") or "",
            body=getattr(slide, "body", "") or "",
            bullets=list(slide.bullets) if slide.bullets else [],
            speaker_notes=getattr(slide, "notes", "") or "",
            image_description=getattr(slide, "image_description", "") or "",
            left_column=getattr(slide, "left_column", "") or "",
            right_column=getattr(slide, "right_column", "") or "",
        )
        # Parse chart_data if present
        chart_data_str = getattr(slide, "chart_data", None)
        if chart_data_str:
            import json
            try:
                spec.chart_data = json.loads(chart_data_str) if isinstance(chart_data_str, str) else chart_data_str
            except (json.JSONDecodeError, TypeError):
                pass
        slides.append(spec)

    return PresentationSpec(
        title=data.title or "Presentation",
        author=getattr(data, "author", "") or "",
        slides=slides,
    )


def from_v2_plan(plan: Any, filled_slides: list[Any] | None = None) -> PresentationSpec:
    """Convert V2 PresentationPlan (with optional FilledSlides) to PresentationSpec.

    V2 model: app.schemas.models.PresentationPlan with SlidePlan items.
    """
    source_slides = filled_slides if filled_slides else plan.slides
    slides = []

    for slide in source_slides:
        # Map V2 SlideType to SlideLayout
        v2_type = slide.slide_type.value if hasattr(slide.slide_type, "value") else str(slide.slide_type)
        layout = _V2_TYPE_TO_LAYOUT.get(v2_type, SlideLayout.CONTENT)

        spec = SlideSpec(
            position=slide.position,
            layout=layout,
            title=slide.headline or "",
            subtitle=getattr(slide, "subheadline", "") or "",
            headline=slide.headline or "",
            subheadline=getattr(slide, "subheadline", "") or "",
            core_message=getattr(slide, "core_message", "") or "",
            speaker_notes=getattr(slide, "speaker_notes", "") or "",
            content_blocks=list(slide.content_blocks) if slide.content_blocks else [],
            visual=slide.visual.model_dump() if hasattr(slide, "visual") and slide.visual else None,
        )

        # Extract image description from visual
        if spec.visual and spec.visual.get("image_description"):
            spec.image_description = spec.visual["image_description"]

        # Extract chart data from visual
        if spec.visual and spec.visual.get("chart_spec"):
            spec.chart_data = spec.visual["chart_spec"]

        # Extract bullets from content_blocks
        for cb in spec.content_blocks:
            if hasattr(cb, "type") and cb.type == "bullets":
                spec.bullets = [item.text for item in cb.items]
                break

        slides.append(spec)

    return PresentationSpec(
        title=plan.slides[0].headline if plan.slides else "Presentation",
        slides=slides,
        audience=plan.audience.value if hasattr(plan.audience, "value") else str(plan.audience),
        image_style=plan.image_style.value if hasattr(plan.image_style, "value") else str(plan.image_style),
    )


# Mapping from V2 SlideType values to unified SlideLayout
_V2_TYPE_TO_LAYOUT: dict[str, SlideLayout] = {
    "title_hero": SlideLayout.TITLE,
    "section_divider": SlideLayout.SECTION,
    "key_statement": SlideLayout.KEY_STATEMENT,
    "bullets_focused": SlideLayout.CONTENT,
    "three_cards": SlideLayout.THREE_CARDS,
    "kpi_dashboard": SlideLayout.KPI_DASHBOARD,
    "image_text_split": SlideLayout.IMAGE,
    "comparison": SlideLayout.COMPARISON,
    "timeline": SlideLayout.TIMELINE,
    "process_flow": SlideLayout.PROCESS_FLOW,
    "chart_insight": SlideLayout.CHART,
    "image_fullbleed": SlideLayout.IMAGE_FULLBLEED,
    "agenda": SlideLayout.AGENDA,
    "closing": SlideLayout.CLOSING,
}
