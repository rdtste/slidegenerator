"""Core domain models for the dual-mode presentation generation system.

These models define the shared vocabulary between Design Mode and Template Mode.
They wrap — but do not replace — the existing V1/V2 schemas.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class LayoutFamily(str, Enum):
    """7 curated layout families with hard word/char budgets.

    Each family defines strict constraints — slides that exceed them
    are blocked by the quality gate and replanned, not truncated.
    """

    HERO = "hero"
    SECTION_DIVIDER = "section_divider"
    TIMELINE = "timeline"
    CARD_GRID = "card_grid"
    COMPARISON = "comparison"
    KEY_FACT = "key_fact"
    CLOSING = "closing"


class VisualRole(str, Enum):
    """Semantic role a visual element plays on a slide.

    Visuals are chosen by role, not by arbitrary LLM prompt.
    """

    HERO_IMAGE = "hero_image"
    SUPPORTING_ICON = "supporting_icon"
    DATA_CHART = "data_chart"
    BACKGROUND_TEXTURE = "background_texture"
    DIAGRAM = "diagram"
    NONE = "none"


# ── Hard budgets per LayoutFamily ────────────────────────────────────────────

LAYOUT_BUDGETS: dict[LayoutFamily, "LayoutBudget"] = {}
"""Populated after LayoutBudget class definition below."""


class LayoutBudget(BaseModel):
    """Hard constraints for a LayoutFamily. Exceeding = block, not truncate."""

    family: LayoutFamily
    max_headline_words: int = Field(8, description="Max words in headline")
    max_headline_chars: int = Field(60, description="Hard char limit for headline")
    max_body_words: int = Field(40, description="Max words in body/supporting text")
    max_body_chars: int = Field(250, description="Hard char limit for body")
    max_bullets: int = Field(5, description="Max bullet points")
    max_bullet_words: int = Field(12, description="Max words per bullet")
    max_total_chars: int = Field(350, description="Hard total char limit for entire slide")
    max_elements: int = Field(4, description="Max content elements (cards, KPIs, steps)")
    dominant_element: str = Field(
        "text",
        description="What should dominate: 'text', 'visual', 'data', 'statement'",
    )
    visual_role: VisualRole = Field(VisualRole.NONE)
    min_whitespace_pct: float = Field(0.30, description="Minimum whitespace ratio")


def _init_budgets() -> None:
    """Initialize the hard budgets for each layout family."""
    LAYOUT_BUDGETS[LayoutFamily.HERO] = LayoutBudget(
        family=LayoutFamily.HERO,
        max_headline_words=10, max_headline_chars=70,
        max_body_words=20, max_body_chars=120,
        max_bullets=0, max_total_chars=200,
        max_elements=1, dominant_element="statement",
        visual_role=VisualRole.HERO_IMAGE, min_whitespace_pct=0.40,
    )
    LAYOUT_BUDGETS[LayoutFamily.SECTION_DIVIDER] = LayoutBudget(
        family=LayoutFamily.SECTION_DIVIDER,
        max_headline_words=6, max_headline_chars=45,
        max_body_words=10, max_body_chars=60,
        max_bullets=0, max_total_chars=110,
        max_elements=1, dominant_element="statement",
        visual_role=VisualRole.NONE, min_whitespace_pct=0.50,
    )
    LAYOUT_BUDGETS[LayoutFamily.TIMELINE] = LayoutBudget(
        family=LayoutFamily.TIMELINE,
        max_headline_words=8, max_headline_chars=60,
        max_body_words=0, max_body_chars=0,
        max_bullets=0, max_total_chars=400,
        max_elements=5, dominant_element="data",
        visual_role=VisualRole.SUPPORTING_ICON, min_whitespace_pct=0.25,
    )
    LAYOUT_BUDGETS[LayoutFamily.CARD_GRID] = LayoutBudget(
        family=LayoutFamily.CARD_GRID,
        max_headline_words=8, max_headline_chars=60,
        max_body_words=0, max_body_chars=0,
        max_bullets=0, max_total_chars=350,
        max_elements=4, dominant_element="text",
        visual_role=VisualRole.SUPPORTING_ICON, min_whitespace_pct=0.25,
    )
    LAYOUT_BUDGETS[LayoutFamily.COMPARISON] = LayoutBudget(
        family=LayoutFamily.COMPARISON,
        max_headline_words=8, max_headline_chars=60,
        max_body_words=30, max_body_chars=180,
        max_bullets=4, max_bullet_words=10,
        max_total_chars=400, max_elements=2,
        dominant_element="text",
        visual_role=VisualRole.NONE, min_whitespace_pct=0.25,
    )
    LAYOUT_BUDGETS[LayoutFamily.KEY_FACT] = LayoutBudget(
        family=LayoutFamily.KEY_FACT,
        max_headline_words=5, max_headline_chars=40,
        max_body_words=25, max_body_chars=150,
        max_bullets=3, max_bullet_words=10,
        max_total_chars=250, max_elements=2,
        dominant_element="statement",
        visual_role=VisualRole.DATA_CHART, min_whitespace_pct=0.35,
    )
    LAYOUT_BUDGETS[LayoutFamily.CLOSING] = LayoutBudget(
        family=LayoutFamily.CLOSING,
        max_headline_words=8, max_headline_chars=60,
        max_body_words=20, max_body_chars=120,
        max_bullets=3, max_bullet_words=10,
        max_total_chars=200, max_elements=2,
        dominant_element="statement",
        visual_role=VisualRole.NONE, min_whitespace_pct=0.40,
    )


_init_budgets()


QUALITY_PASS_THRESHOLD: float = 70.0


class QualityScore(BaseModel):
    """Quality assessment for a single slide or entire deck.

    score < QUALITY_PASS_THRESHOLD (70) = HARD BLOCK (not warning).
    """

    score: float = Field(100.0, ge=0, le=100)
    readability: float = Field(100.0, ge=0, le=100)
    density: float = Field(100.0, ge=0, le=100)
    hierarchy: float = Field(100.0, ge=0, le=100)
    balance: float = Field(100.0, ge=0, le=100)
    visual_fit: float = Field(100.0, ge=0, le=100)
    budget_compliance: float = Field(100.0, ge=0, le=100)
    violations: list[str] = Field(default_factory=list)

    @property
    def passed(self) -> bool:
        return self.score >= QUALITY_PASS_THRESHOLD

    @property
    def blocked(self) -> bool:
        return not self.passed


class CompressedSlideSpec(BaseModel):
    """A slide specification after content compression.

    The compressor transforms raw LLM output into this constrained form.
    Every field respects the LayoutBudget of the assigned family.
    """

    position: int = Field(1, ge=1)
    layout_family: LayoutFamily
    core_assertion: str = Field("", description="The ONE thing this slide communicates")
    headline: str = Field("")
    supporting_text: str = Field("", description="Compressed body text")
    bullets: list[str] = Field(default_factory=list)
    elements: list[dict] = Field(
        default_factory=list,
        description="Cards, KPIs, timeline entries — max per budget",
    )
    visual_role: VisualRole = Field(VisualRole.NONE)
    visual_description: str = Field("")
    speaker_notes: str = Field("")
    original_char_count: int = Field(0, description="Chars before compression")
    compressed_char_count: int = Field(0, description="Chars after compression")
    compression_ratio: float = Field(1.0, description="original / compressed")

    @property
    def budget(self) -> LayoutBudget:
        return LAYOUT_BUDGETS[self.layout_family]

    def exceeds_budget(self) -> list[str]:
        """Check which budget constraints are violated."""
        violations = []
        b = self.budget
        hw = len(self.headline.split())
        if hw > b.max_headline_words:
            violations.append(f"headline_words: {hw}/{b.max_headline_words}")
        if len(self.headline) > b.max_headline_chars:
            violations.append(f"headline_chars: {len(self.headline)}/{b.max_headline_chars}")
        bw = len(self.supporting_text.split())
        if bw > b.max_body_words:
            violations.append(f"body_words: {bw}/{b.max_body_words}")
        if len(self.bullets) > b.max_bullets:
            violations.append(f"bullets: {len(self.bullets)}/{b.max_bullets}")
        for i, bullet in enumerate(self.bullets):
            if len(bullet.split()) > b.max_bullet_words:
                violations.append(f"bullet_{i}_words: {len(bullet.split())}/{b.max_bullet_words}")
        if len(self.elements) > b.max_elements:
            violations.append(f"elements: {len(self.elements)}/{b.max_elements}")
        total = len(self.headline) + len(self.supporting_text) + sum(len(b) for b in self.bullets)
        total += sum(len(str(e)) for e in self.elements)
        if total > b.max_total_chars:
            violations.append(f"total_chars: {total}/{b.max_total_chars}")
        return violations


class GenerationMode(str, Enum):
    """The two primary generation modes."""

    DESIGN = "design"
    """AI-driven pipeline producing visually excellent presentations.
    Template optional (provides theme colors/fonts).
    Uses blueprint-based layout with LLM content generation."""

    TEMPLATE = "template"
    """Deterministic pipeline filling corporate template placeholders.
    Template required (defines all layouts and constraints).
    No LLM for layout decisions — mapping is analyzed and stored."""


class RenderMode(str, Enum):
    """How the final PPTX is rendered."""

    BLUEPRINT = "blueprint"
    """Design Mode: shapes/textboxes positioned by blueprint system."""

    PLACEHOLDER = "placeholder"
    """Template Mode: content placed into template placeholders."""


class PresentationRequest(BaseModel):
    """Unified request model for both generation modes.

    This is the entry point to the generation system. The `mode` field
    determines which pipeline processes the request.
    """

    prompt: str = Field(..., description="User prompt / briefing text")
    mode: GenerationMode = Field(
        GenerationMode.DESIGN,
        description="Generation mode: 'design' for AI-driven, 'template' for corporate filling",
    )
    template_id: str | None = Field(
        None,
        description="Template ID. Required for template mode, optional for design mode.",
    )
    document_text: str = Field("", description="Extracted document text (optional)")
    audience: str = Field("management", description="Target audience")
    image_style: str = Field("minimal", description="Image style preference")
    accent_color: str = Field("#2563EB", description="Accent color hex")
    font_family: str = Field("Calibri", description="Font family")

    def validate_for_mode(self) -> list[str]:
        """Validate that the request is consistent with the selected mode."""
        errors: list[str] = []
        if self.mode == GenerationMode.TEMPLATE and not self.template_id:
            errors.append("template_id is required for template mode")
        if not self.prompt or not self.prompt.strip():
            errors.append("prompt must not be empty")
        return errors


class GenerationResult(BaseModel):
    """Unified result from both generation modes."""

    pptx_path: str = Field(..., description="Path to the generated PPTX file")
    mode: GenerationMode
    slide_count: int = Field(0)
    quality_score: float = Field(100.0)
    quality_passed: bool = Field(True)
    design_score: float | None = Field(None)
    warnings: list[str] = Field(default_factory=list)
    timings: dict[str, float] = Field(default_factory=dict)


class BrandTheme(BaseModel):
    """Brand/theme information extracted from a template or provided explicitly.

    Used by Design Mode to apply corporate colors/fonts without
    constraining layouts to template placeholders.
    """

    primary_color: str = "#2563EB"
    accent_colors: list[str] = Field(default_factory=list)
    background_color: str = "#FFFFFF"
    text_color: str = "#333333"
    heading_color: str = "#1a1a2e"
    heading_font: str = "Calibri"
    body_font: str = "Calibri"
    chart_colors: list[str] = Field(default_factory=list)

    @classmethod
    def from_template_profile(cls, profile: dict) -> BrandTheme:
        """Create a BrandTheme from a TemplateProfile dict."""
        color_dna = profile.get("color_dna", {})
        typo_dna = profile.get("typography_dna", {})
        return cls(
            primary_color=color_dna.get("accent1", "#2563EB"),
            accent_colors=[
                color_dna.get(f"accent{i}", "") for i in range(1, 7)
                if color_dna.get(f"accent{i}")
            ],
            background_color=color_dna.get("background", "#FFFFFF"),
            text_color=color_dna.get("text", "#333333"),
            heading_color=color_dna.get("heading", "#1a1a2e"),
            heading_font=typo_dna.get("heading_font", "Calibri"),
            body_font=typo_dna.get("body_font", "Calibri"),
            chart_colors=color_dna.get("chart_colors", []),
        )
