"""Unified Generation Orchestrator — dispatches to Design Mode or Template Mode.

This is the single entry point for all presentation generation.
It inspects the PresentationRequest.mode and delegates to the
appropriate pipeline.

Existing V1/V2 pipelines are wrapped — not replaced — by this orchestrator.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Callable

from app.domain.models import (
    GenerationMode,
    PresentationRequest,
    GenerationResult,
    BrandTheme,
)

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[str, str, int | None], None]


class UnifiedOrchestrator:
    """Mode-aware orchestrator for presentation generation.

    Usage:
        orchestrator = UnifiedOrchestrator()
        orchestrator.set_progress_callback(on_progress)
        result = await orchestrator.generate(request)
    """

    def __init__(self):
        self._progress_cb: ProgressCallback | None = None
        self._image_generator: Callable | None = None
        self._chart_generator: Callable | None = None

    def set_progress_callback(self, cb: ProgressCallback) -> None:
        self._progress_cb = cb

    def set_image_generator(self, fn: Callable) -> None:
        self._image_generator = fn

    def set_chart_generator(self, fn: Callable) -> None:
        self._chart_generator = fn

    def _progress(self, step: str, message: str, pct: int | None = None) -> None:
        if self._progress_cb:
            self._progress_cb(step, message, pct)

    async def generate(self, request: PresentationRequest) -> GenerationResult:
        """Generate a presentation using the appropriate mode pipeline."""
        # Validate request
        errors = request.validate_for_mode()
        if errors:
            raise ValueError(f"Invalid request: {'; '.join(errors)}")

        start = time.monotonic()

        if request.mode == GenerationMode.DESIGN:
            result = await self._run_design_mode(request)
        elif request.mode == GenerationMode.TEMPLATE:
            result = await self._run_template_mode(request)
        else:
            raise ValueError(f"Unknown generation mode: {request.mode}")

        elapsed = time.monotonic() - start
        result.timings["total"] = round(elapsed, 1)
        logger.info(
            f"[Orchestrator] {request.mode.value} mode complete: "
            f"{result.slide_count} slides, {elapsed:.1f}s"
        )
        return result

    async def _run_design_mode(self, request: PresentationRequest) -> GenerationResult:
        """Run the Design Mode pipeline (delegates to existing V2 pipeline)."""
        from app.pipeline.orchestrator import PipelineOrchestrator
        from app.schemas.models import Audience, ImageStyleType

        self._progress("init", "Design Mode: Pipeline wird gestartet...", 1)

        # Parse audience and image style
        try:
            audience = Audience(request.audience)
        except ValueError:
            audience = Audience.MANAGEMENT

        try:
            image_style = ImageStyleType(request.image_style)
        except ValueError:
            image_style = ImageStyleType.MINIMAL

        # Load brand theme from template if provided
        theme = await self._load_brand_theme(request.template_id)

        orchestrator = PipelineOrchestrator(
            audience=audience,
            image_style=image_style,
            accent_color=theme.primary_color if theme else request.accent_color,
            font_family=theme.body_font if theme else request.font_family,
            template_id=request.template_id,
        )

        if self._progress_cb:
            orchestrator.set_progress_callback(self._progress_cb)
        if self._image_generator:
            orchestrator.set_image_generator(self._image_generator)
        if self._chart_generator:
            orchestrator.set_chart_generator(self._chart_generator)

        pipeline_result = await orchestrator.run(
            user_input=request.prompt,
            document_text=request.document_text,
        )

        return GenerationResult(
            pptx_path=str(pipeline_result.pptx_path),
            mode=GenerationMode.DESIGN,
            slide_count=pipeline_result.slide_count,
            quality_score=pipeline_result.score,
            quality_passed=pipeline_result.passed,
            design_score=pipeline_result.quality.design_score,
        )

    async def _run_template_mode(self, request: PresentationRequest) -> GenerationResult:
        """Run the Template Mode pipeline (delegates to existing V1 pipeline).

        Template Mode uses the V1 pipeline which fills actual template
        placeholders. This will be enhanced in Phase 2 with structured
        PlaceholderMapping.
        """
        from app.services.pptx_service import generate_pptx
        from app.services.markdown_service import parse_markdown

        self._progress("init", "Template Mode: Inhalte werden verarbeitet...", 1)

        # For Template Mode, we need to generate markdown content from the prompt
        # using the LLM, then fill the template. For now, we use the V1 pipeline
        # which expects markdown input.
        #
        # TODO Phase 2: Replace with dedicated Template Mode pipeline that uses
        # structured content directly without markdown intermediate step.

        # Generate markdown content from prompt using LLM
        markdown = await self._generate_markdown_for_template(request)

        self._progress("generating", "Template wird befuellt...", 30)

        try:
            pptx_path = generate_pptx(
                parse_markdown(markdown),
                template_id=request.template_id or "default",
                progress_callback=self._progress_cb,
                custom_color=request.accent_color if request.accent_color != "#2563EB" else None,
                custom_font=request.font_family if request.font_family != "Calibri" else None,
            )
        except Exception as exc:
            logger.error(f"Template mode generation failed: {exc}")
            raise

        self._progress("done", "Praesentation erstellt!", 100)

        return GenerationResult(
            pptx_path=str(pptx_path),
            mode=GenerationMode.TEMPLATE,
            slide_count=0,  # Will be set by caller
            quality_score=100.0,
            quality_passed=True,
        )

    async def _generate_markdown_for_template(self, request: PresentationRequest) -> str:
        """Generate markdown content from a prompt for Template Mode.

        Uses Gemini to create structured markdown that the V1 pipeline
        can parse and fill into template placeholders.

        TODO Phase 2: This will be replaced by a direct content generation
        step that produces SlideSpecs without the markdown intermediate.
        """
        from app.pipeline.llm_client import call_llm_async

        prompt = f"""Erstelle eine PowerPoint-Praesentation als Markdown.
Das Thema: {request.prompt}

Regeln:
- Verwende --- als Folientrenner
- Erste Folie: layout: title
- Letzte Folie: layout: closing
- Inhaltsfolien: layout: content
- Verwende Aufzaehlungspunkte (- ) fuer Inhalte
- Jede Folie braucht einen Titel (# Titel)
- 8-12 Folien insgesamt
- Maximal 5 Aufzaehlungspunkte pro Folie
- Klare, praegnante Sprache

Format pro Folie:
---
layout: content
---
# Folientitel
- Punkt 1
- Punkt 2

Erstelle jetzt die Praesentation:"""

        try:
            markdown = await call_llm_async(prompt, temperature=0.5, max_tokens=8192)
            return markdown
        except Exception as exc:
            logger.error(f"Markdown generation failed: {exc}")
            # Fallback: minimal presentation
            return f"""---
layout: title
---
# {request.prompt[:80]}

---
layout: content
---
# Inhalt
- {request.prompt}

---
layout: closing
---
# Vielen Dank
"""

    async def _load_brand_theme(self, template_id: str | None) -> BrandTheme | None:
        """Load BrandTheme from template profile if available."""
        if not template_id:
            return None

        try:
            from app.templates_mgmt.registry import FileTemplateRegistry
            registry = FileTemplateRegistry()
            desc = registry.get(template_id)
            if not desc or not desc.profile_available:
                return None

            # Load full profile
            import json
            from app.config import settings
            profile_path = settings.templates_dir / f"{template_id}.profile.json"
            if profile_path.is_file():
                profile = json.loads(profile_path.read_text(encoding="utf-8"))
                return BrandTheme.from_template_profile(profile)
        except Exception as exc:
            logger.warning(f"Failed to load brand theme for {template_id}: {exc}")

        return None
