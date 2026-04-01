"""Template management domain models.

Consolidates all template-related data models:
- TemplateDescriptor: registry-level metadata
- PlaceholderSlot / LayoutMapping / TemplatePlaceholderMap: placeholder mapping for Template Mode
- ColorDNA / TypographyDNA / LayoutDetail / PlaceholderDetail: deep profile models
- ChartGuidelines / ImageGuidelines / TemplateProfile: profiling output
"""

from __future__ import annotations

from pydantic import BaseModel, Field


# ── Registry models ──────────────────────────────────────────────────────

class TemplateDescriptor(BaseModel):
    """Metadata about a registered template.

    This extends the existing .meta.json with version tracking
    and profile references.
    """

    id: str
    name: str = ""
    filename: str = ""
    version: int = Field(1, ge=1)
    scope: str = Field("global")  # "global" | "session"
    session_id: str | None = None
    uploaded_at: str = ""
    profile_available: bool = False
    layout_count: int = 0
    supported_types: list[str] = Field(default_factory=list)


class PlaceholderSlot(BaseModel):
    """A single placeholder slot in a template layout."""

    role: str = ""  # "title", "body", "bullets", "image", "chart"
    ph_index: int = 0
    ph_type: int = 0  # OOXML placeholder type constant
    max_chars: int = 0
    width_cm: float = 0.0
    height_cm: float = 0.0
    position: str = ""  # "left", "right", "center", "full-width"


class LayoutMapping(BaseModel):
    """Mapping from a semantic layout type to a template layout with placeholder assignments."""

    layout_index: int
    layout_name: str = ""
    semantic_type: str = ""  # "title", "content", "image", etc.
    confidence: float = Field(1.0, ge=0, le=1)
    slots: list[PlaceholderSlot] = Field(default_factory=list)
    max_bullets: int = 0
    max_chars_per_bullet: int = 0
    title_max_chars: int = 0


class TemplatePlaceholderMap(BaseModel):
    """Complete placeholder mapping for a template.

    This is the key artifact that makes Template Mode deterministic:
    given a semantic layout type (e.g., "content"), this mapping tells
    exactly which template layout to use and which placeholders to fill.
    """

    template_id: str
    template_version: int = 1
    layouts: list[LayoutMapping] = Field(default_factory=list)

    def get_mapping(self, semantic_type: str) -> LayoutMapping | None:
        """Find the best layout mapping for a semantic type."""
        candidates = [lm for lm in self.layouts if lm.semantic_type == semantic_type]
        if not candidates:
            return None
        # Return highest confidence match
        return max(candidates, key=lambda lm: lm.confidence)

    def get_layout_index(self, semantic_type: str) -> int | None:
        """Get the template layout index for a semantic type."""
        mapping = self.get_mapping(semantic_type)
        return mapping.layout_index if mapping else None


# ── Profile models (deep template analysis) ──────────────────────────────

class ColorDNA(BaseModel):
    """Full color information extracted from the template theme."""
    primary: str = "#000000"
    secondary: str = "#333333"
    accent1: str = "#0969da"
    accent2: str = "#22c55e"
    accent3: str = "#f59e0b"
    accent4: str = "#ef4444"
    accent5: str = "#8b5cf6"
    accent6: str = "#06b6d4"
    background: str = "#FFFFFF"
    text: str = "#000000"
    heading: str = "#000000"
    chart_colors: list[str] = Field(default_factory=list,
        description="Ordered color sequence for chart series/data points")
    hyperlink: str = "#0969da"


class TypographyDNA(BaseModel):
    """Font and text style information from the template."""
    heading_font: str = "Calibri"
    body_font: str = "Calibri"
    heading_sizes_pt: list[float] = Field(default_factory=list)
    body_sizes_pt: list[float] = Field(default_factory=list)
    bullet_indent_cm: float = 0.0
    line_spacing_factor: float = 1.2


class PlaceholderDetail(BaseModel):
    """Detailed information about a single placeholder in a layout."""
    type: str = ""
    index: int = 0
    left_cm: float = 0.0
    top_cm: float = 0.0
    width_cm: float = 0.0
    height_cm: float = 0.0
    font_sizes_pt: list[float] = Field(default_factory=list)
    position: str = ""  # "left", "right", "top", "bottom", "center", "full-width"


class LayoutDetail(BaseModel):
    """Detailed classification of a single layout."""
    index: int
    name: str
    mapped_type: str = ""
    description: str = ""
    recommended_usage: str = ""
    has_picture: bool = False
    has_chart: bool = False
    has_table: bool = False
    picture_aspect_ratio: str = ""
    picture_width_cm: float = 0.0
    picture_height_cm: float = 0.0
    content_width_cm: float = 0.0
    content_height_cm: float = 0.0
    max_bullets: int = 0
    max_chars_per_bullet: int = 0
    title_max_chars: int = 0
    placeholder_types: list[str] = Field(default_factory=list)
    placeholder_details: list[PlaceholderDetail] = Field(default_factory=list)
    spatial_description: str = ""  # AI-generated: "Picture left (50%), content right (50%)"
    generation_rules: str = ""  # AI-generated: specific rules for filling this layout


class ChartGuidelines(BaseModel):
    """Guidelines for chart/diagram generation aligned with template style."""
    color_sequence: list[str] = Field(default_factory=list)
    font_family: str = "Calibri"
    font_size_pt: float = 10.0
    background_color: str = "transparent"
    grid_color: str = "#E0E0E0"
    text_color: str = "#333333"
    style: str = "modern_flat"
    available_chart_layouts: list[int] = Field(default_factory=list)


class ImageGuidelines(BaseModel):
    """Guidelines for image generation aligned with template style."""
    available_image_layouts: list[int] = Field(default_factory=list)
    primary_aspect_ratio: str = "16:9"
    style_keywords: list[str] = Field(default_factory=list)
    accent_color: str = "#0969da"


class TemplateProfile(BaseModel):
    """Comprehensive profile of a learned template — the result of deep analysis."""
    template_id: str
    template_name: str = ""
    description: str = ""
    design_personality: str = ""
    slide_width_cm: float = 33.9
    slide_height_cm: float = 19.1
    color_dna: ColorDNA = Field(default_factory=ColorDNA)
    typography_dna: TypographyDNA = Field(default_factory=TypographyDNA)
    layout_catalog: list[LayoutDetail] = Field(default_factory=list)
    chart_guidelines: ChartGuidelines = Field(default_factory=ChartGuidelines)
    image_guidelines: ImageGuidelines = Field(default_factory=ImageGuidelines)
    supported_layout_types: list[str] = Field(default_factory=list)
    design_rules: dict[str, str] = Field(default_factory=dict,
        description="Overarching design quality rules (title_rules, bullet_rules, image_rules, etc.)")
    guidelines: str = ""
    learned_at: str = ""
