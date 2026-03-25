"""Slide-type registry — canonical constraints for every allowed slide type."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.schemas.models import SlideType


@dataclass(frozen=True)
class SlideTypeDefinition:
    """Immutable definition of a single slide type and its constraints."""

    name: SlideType
    purpose: str
    allowed_content_block_types: list[str] = field(default_factory=list)
    max_content_blocks: int = 0
    max_total_chars: int = 200
    allows_image: bool = False
    allows_chart: bool = False
    required_fields: list[str] = field(default_factory=list)
    forbidden_fields: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

SLIDE_TYPE_REGISTRY: dict[SlideType, SlideTypeDefinition] = {
    SlideType.TITLE_HERO: SlideTypeDefinition(
        name=SlideType.TITLE_HERO,
        purpose="Opening title slide with optional hero image",
        allowed_content_block_types=[],
        max_content_blocks=0,
        max_total_chars=130,
        allows_image=True,
        allows_chart=False,
        required_fields=["headline"],
        forbidden_fields=[],
    ),
    SlideType.SECTION_DIVIDER: SlideTypeDefinition(
        name=SlideType.SECTION_DIVIDER,
        purpose="Visual break between major sections",
        allowed_content_block_types=[],
        max_content_blocks=0,
        max_total_chars=100,
        allows_image=False,
        allows_chart=False,
        required_fields=["headline"],
        forbidden_fields=[],
    ),
    SlideType.KEY_STATEMENT: SlideTypeDefinition(
        name=SlideType.KEY_STATEMENT,
        purpose="Single powerful statement or quote",
        allowed_content_block_types=["quote"],
        max_content_blocks=1,
        max_total_chars=150,
        allows_image=False,
        allows_chart=False,
        required_fields=["headline"],
        forbidden_fields=[],
    ),
    SlideType.BULLETS_FOCUSED: SlideTypeDefinition(
        name=SlideType.BULLETS_FOCUSED,
        purpose="Concise bullet-point slide for key takeaways",
        allowed_content_block_types=["bullets"],
        max_content_blocks=3,
        max_total_chars=250,
        allows_image=False,
        allows_chart=False,
        required_fields=["headline"],
        forbidden_fields=[],
    ),
    SlideType.THREE_CARDS: SlideTypeDefinition(
        name=SlideType.THREE_CARDS,
        purpose="Three equal cards with icon, title and body",
        allowed_content_block_types=["card"],
        max_content_blocks=3,
        max_total_chars=400,
        allows_image=False,
        allows_chart=False,
        required_fields=["headline"],
        forbidden_fields=[],
    ),
    SlideType.KPI_DASHBOARD: SlideTypeDefinition(
        name=SlideType.KPI_DASHBOARD,
        purpose="Dashboard of 2-5 key performance indicators",
        allowed_content_block_types=["kpi"],
        max_content_blocks=5,
        max_total_chars=300,
        allows_image=False,
        allows_chart=False,
        required_fields=["headline"],
        forbidden_fields=[],
    ),
    SlideType.IMAGE_TEXT_SPLIT: SlideTypeDefinition(
        name=SlideType.IMAGE_TEXT_SPLIT,
        purpose="Half image, half text for supporting or evidence visuals",
        allowed_content_block_types=["bullets", "text"],
        max_content_blocks=1,
        max_total_chars=250,
        allows_image=True,
        allows_chart=False,
        required_fields=["headline"],
        forbidden_fields=[],
    ),
    SlideType.COMPARISON: SlideTypeDefinition(
        name=SlideType.COMPARISON,
        purpose="Side-by-side comparison of two options or states",
        allowed_content_block_types=["comparison_column"],
        max_content_blocks=2,
        max_total_chars=350,
        allows_image=False,
        allows_chart=False,
        required_fields=["headline"],
        forbidden_fields=[],
    ),
    SlideType.TIMELINE: SlideTypeDefinition(
        name=SlideType.TIMELINE,
        purpose="Chronological sequence of 3-6 events or milestones",
        allowed_content_block_types=["timeline_entry"],
        max_content_blocks=6,
        max_total_chars=500,
        allows_image=False,
        allows_chart=False,
        required_fields=["headline"],
        forbidden_fields=[],
    ),
    SlideType.PROCESS_FLOW: SlideTypeDefinition(
        name=SlideType.PROCESS_FLOW,
        purpose="Step-by-step process visualization (3-5 steps)",
        allowed_content_block_types=["process_step"],
        max_content_blocks=5,
        max_total_chars=450,
        allows_image=False,
        allows_chart=False,
        required_fields=["headline"],
        forbidden_fields=[],
    ),
    SlideType.CHART_INSIGHT: SlideTypeDefinition(
        name=SlideType.CHART_INSIGHT,
        purpose="Data chart with concise bullet commentary",
        allowed_content_block_types=["bullets"],
        max_content_blocks=2,
        max_total_chars=200,
        allows_image=False,
        allows_chart=True,
        required_fields=["headline"],
        forbidden_fields=[],
    ),
    SlideType.IMAGE_FULLBLEED: SlideTypeDefinition(
        name=SlideType.IMAGE_FULLBLEED,
        purpose="Full-bleed hero image with minimal overlay text",
        allowed_content_block_types=["text"],
        max_content_blocks=1,
        max_total_chars=60,
        allows_image=True,
        allows_chart=False,
        required_fields=["headline"],
        forbidden_fields=[],
    ),
    SlideType.AGENDA: SlideTypeDefinition(
        name=SlideType.AGENDA,
        purpose="Agenda or table of contents (3-6 items)",
        allowed_content_block_types=["bullets"],
        max_content_blocks=6,
        max_total_chars=280,
        allows_image=False,
        allows_chart=False,
        required_fields=["headline"],
        forbidden_fields=[],
    ),
    SlideType.CLOSING: SlideTypeDefinition(
        name=SlideType.CLOSING,
        purpose="Closing slide with summary bullets or call to action",
        allowed_content_block_types=["bullets"],
        max_content_blocks=3,
        max_total_chars=250,
        allows_image=False,
        allows_chart=False,
        required_fields=["headline"],
        forbidden_fields=[],
    ),
}


def get_type_def(slide_type: SlideType) -> SlideTypeDefinition:
    """Return the canonical definition for *slide_type*.

    Raises ``KeyError`` if the type is not registered.
    """
    return SLIDE_TYPE_REGISTRY[slide_type]
