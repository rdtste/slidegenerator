from __future__ import annotations

from pydantic import BaseModel, Field


# --- Slides ---

class SlideContent(BaseModel):
    layout: str = Field("content", description="Slide layout type: title, section, content, two_column, image, chart, closing")
    title: str = Field("", description="Slide title / heading")
    subtitle: str = Field("", description="Subtitle or subheading")
    body: str = Field("", description="Body text (Markdown)")
    bullets: list[str] = Field(default_factory=list, description="Bullet points")
    notes: str = Field("", description="Presenter notes")
    image_description: str = Field("", description="Description/placeholder for image")
    chart_data: str = Field("", description="JSON chart data for chart layout")
    left_column: str = Field("", description="Left column content (two_column layout)")
    right_column: str = Field("", description="Right column content (two_column layout)")


class PresentationData(BaseModel):
    title: str = Field("Presentation", description="Presentation title")
    author: str = Field("", description="Author name")
    slides: list[SlideContent] = Field(default_factory=list)


# --- Generate ---

class GenerateRequest(BaseModel):
    markdown: str = Field(..., min_length=1, description="Marp-style Markdown")
    template_id: str = Field("default", description="Template to use")
    custom_color: str | None = Field(None, description="Accent color hex (e.g. #7BA7D9)")
    custom_font: str | None = Field(None, description="Font family (e.g. Calibri)")


class GenerateResponse(BaseModel):
    filename: str
    download_url: str


# --- Templates ---

class TemplateInfo(BaseModel):
    id: str
    name: str
    description: str = ""
    layouts: list[str] = Field(default_factory=list, description="Available slide layout names")
    preview_url: str = ""


# --- Template Structure (raw layout metadata for AI analysis) ---

class PlaceholderInfo(BaseModel):
    index: int
    type_id: int
    type_name: str
    name: str
    width_cm: float
    height_cm: float
    left_cm: float
    top_cm: float
    font_sizes_pt: list[float] = Field(default_factory=list)


class LayoutInfo(BaseModel):
    index: int
    name: str
    placeholders: list[PlaceholderInfo] = Field(default_factory=list)


class TemplateStructure(BaseModel):
    template_id: str
    slide_width_cm: float
    slide_height_cm: float
    layouts: list[LayoutInfo] = Field(default_factory=list)
