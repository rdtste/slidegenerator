"""Core domain models for the dual-mode presentation generation system.

These models define the shared vocabulary between Design Mode and Template Mode.
They wrap — but do not replace — the existing V1/V2 schemas.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


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
