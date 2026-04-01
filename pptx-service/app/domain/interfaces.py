"""Interfaces (Protocols) for the dual-mode presentation generation system.

These define the contracts between modules. Implementations can be swapped
without changing consumers.

Using Python Protocols (structural subtyping) — no base class inheritance needed.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable, Callable, Any

from app.domain.models import PresentationRequest, GenerationResult, BrandTheme


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

@runtime_checkable
class PresentationRenderer(Protocol):
    """Renders a presentation to a PPTX file.

    Design Mode and Template Mode each have their own renderer implementation.
    """

    def render(
        self,
        slides: list[Any],
        output_dir: Path | None = None,
        progress_callback: Callable[[str, str, int | None], None] | None = None,
    ) -> Path:
        """Render slides to a PPTX file and return the output path."""
        ...


# ---------------------------------------------------------------------------
# Template Analysis
# ---------------------------------------------------------------------------

@runtime_checkable
class TemplateAnalyzer(Protocol):
    """Analyzes a PowerPoint template and extracts its visual profile."""

    def analyze(self, template_path: Path) -> dict:
        """Analyze a template file and return its profile as a dict.

        The returned dict should contain at minimum:
        - color_dna: ColorDNA
        - typography_dna: TypographyDNA
        - layout_catalog: list of LayoutDetail
        - supported_layout_types: list of str
        """
        ...


# ---------------------------------------------------------------------------
# Template Registry
# ---------------------------------------------------------------------------

@runtime_checkable
class TemplateRegistry(Protocol):
    """Manages template metadata and lookup."""

    def get(self, template_id: str) -> dict | None:
        """Get a template descriptor by ID. Returns None if not found."""
        ...

    def list_all(self) -> list[dict]:
        """List all registered templates."""
        ...

    def register(self, template_id: str, metadata: dict) -> None:
        """Register or update a template in the registry."""
        ...


# ---------------------------------------------------------------------------
# Slide Planning
# ---------------------------------------------------------------------------

@runtime_checkable
class SlidePlanner(Protocol):
    """Plans the slide structure for a presentation.

    Design Mode uses AI-driven planning.
    Template Mode uses deterministic mapping.
    """

    async def plan(
        self,
        request: PresentationRequest,
        theme: BrandTheme | None = None,
    ) -> list[Any]:
        """Plan the slide structure and return a list of slide specs."""
        ...


# ---------------------------------------------------------------------------
# Content Mapper (Template Mode)
# ---------------------------------------------------------------------------

@runtime_checkable
class ContentMapper(Protocol):
    """Maps content to template placeholder slots.

    Used by Template Mode to determine which content goes into
    which placeholder of which layout.
    """

    def map_content(
        self,
        slide_content: Any,
        layout_mapping: dict,
    ) -> dict[int, Any]:
        """Map slide content to placeholder indices.

        Returns: {placeholder_index: content_value}
        """
        ...


# ---------------------------------------------------------------------------
# Generation Pipeline
# ---------------------------------------------------------------------------

@runtime_checkable
class GenerationPipeline(Protocol):
    """A complete generation pipeline (Design or Template mode)."""

    async def run(
        self,
        request: PresentationRequest,
        progress_callback: Callable[[str, str, int | None], None] | None = None,
    ) -> GenerationResult:
        """Run the full generation pipeline and return the result."""
        ...
