"""V2 Pipeline Orchestrator — 8-stage production pipeline for presentations.

Stages:
1. Input Interpreter (LLM)
2. Storyline Planner (LLM)
3. Slide Planner (LLM, constrained)
4. Schema Validator (Code)
5. Content Filler (LLM, per-slide)
6. Layout Engine (Code)
7. PPTX Renderer (Code)
8. Post-Generation Review (Code + optional LLM)
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Callable

from app.schemas.models import (
    InterpretedBriefing, Storyline, PresentationPlan, SlidePlan,
    FilledSlide, RenderInstruction, QualityReport,
    SlideType, Audience, ImageStyleType, TextMetrics,
    BulletsBlock, KpiBlock, TextBlock, CardBlock, QuoteBlock,
    ComparisonColumnBlock, TimelineEntryBlock, ProcessStepBlock,
)
from app.layouts.engine import LayoutEngine
from app.renderers.pptx_renderer_v2 import PptxRendererV2
from app.compression.content_compressor import compress_presentation
from app.quality.quality_gate import QualityGate, GateResult, GateVerdict
from app.quality.replan_engine import ReplanEngine
from app.domain.models import CompressedSlideSpec

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[str, str, int | None], None]

MAX_REGEN_ATTEMPTS = 2


class PipelineOrchestrator:
    """Orchestrates the full presentation generation pipeline."""

    def __init__(
        self,
        audience: Audience = Audience.MANAGEMENT,
        image_style: ImageStyleType = ImageStyleType.MINIMAL,
        accent_color: str = "#2563EB",
        font_family: str = "Calibri",
        template_id: str | None = None,
    ):
        self.audience = audience
        self.image_style = image_style
        self.accent_color = accent_color
        self.font_family = font_family
        self.template_id = template_id

        self.layout_engine = LayoutEngine(accent_color=accent_color, font_family=font_family)
        self.renderer = PptxRendererV2(accent_color=accent_color, font_family=font_family,
                                       template_id=template_id)

        self._progress_cb: ProgressCallback | None = None
        self._image_generator: Callable | None = None
        self._chart_generator: Callable | None = None

    def set_progress_callback(self, cb: ProgressCallback) -> None:
        self._progress_cb = cb

    def set_image_generator(self, fn: Callable) -> None:
        self._image_generator = fn
        self.renderer.set_image_generator(fn)

    def set_chart_generator(self, fn: Callable) -> None:
        self._chart_generator = fn
        self.renderer.set_chart_generator(fn)

    def _progress(self, step: str, message: str, pct: int | None = None) -> None:
        if self._progress_cb:
            self._progress_cb(step, message, pct)
        logger.info(f"[Pipeline] {step}: {message}")

    async def run(self, user_input: str, document_text: str = "",
                  output_dir: str | None = None) -> PipelineResult:
        """Execute the full pipeline."""
        pipeline_start = time.monotonic()
        timings: dict[str, float] = {}

        def _timed(name: str) -> float:
            t = time.monotonic()
            timings[name] = t - pipeline_start
            return t

        # ── Stage 1: Input Interpretation ──
        self._progress("stage_1", "Briefing wird analysiert...", 2)
        t0 = time.monotonic()
        briefing = await self._stage_1_interpret(user_input, document_text)
        briefing.audience = self.audience
        briefing.image_style = self.image_style
        logger.info(f"[Timing] Stage 1 (interpret): {time.monotonic() - t0:.1f}s")

        # ── Stage 2: Storyline Planning ──
        self._progress("stage_2", "Storyline wird geplant...", 10)
        t0 = time.monotonic()
        storyline = await self._stage_2_storyline(briefing)
        logger.info(f"[Timing] Stage 2 (storyline): {time.monotonic() - t0:.1f}s")

        # ── Stage 3: Slide Planning ──
        self._progress("stage_3", "Folien werden geplant...", 20)
        t0 = time.monotonic()
        plan = await self._stage_3_slide_plan(storyline, briefing)
        logger.info(f"[Timing] Stage 3 (slide plan): {time.monotonic() - t0:.1f}s")

        # ── Stage 4: Schema Validation ──
        self._progress("stage_4", "Validierung...", 30)
        t0 = time.monotonic()
        plan, quality = await self._stage_4_validate(plan, storyline, briefing)
        logger.info(f"[Timing] Stage 4 (validate): {time.monotonic() - t0:.1f}s")

        # ── Stage 4b: Content Compression ──
        self._progress("stage_4b", "Inhalte werden komprimiert...", 35)
        t0 = time.monotonic()
        compressed_slides = self._stage_4b_compress(plan)
        logger.info(f"[Timing] Stage 4b (compression): {time.monotonic() - t0:.1f}s")

        # ── Stage 4c: Hard Quality Gate + Replan ──
        self._progress("stage_4c", "Qualitaetspruefung (Hard Gate)...", 38)
        t0 = time.monotonic()
        compressed_slides, gate_result = self._stage_4c_quality_gate(compressed_slides)
        if not gate_result.passed:
            logger.warning(
                f"[Pipeline] Quality gate: {gate_result.blocked_count} slides blocked, "
                f"replanned. Overall: {gate_result.overall_score:.0f}/100"
            )
        logger.info(f"[Timing] Stage 4c (quality gate): {time.monotonic() - t0:.1f}s")

        # ── Stage 5: Content Filling ──
        self._progress("stage_5", "Texte werden finalisiert...", 40)
        t0 = time.monotonic()
        filled_slides = await self._stage_5_fill_content(plan)
        logger.info(f"[Timing] Stage 5 (content fill, {len(plan.slides)} slides): {time.monotonic() - t0:.1f}s")

        # ── Stage 6: Layout Engine ──
        self._progress("stage_6", "Layouts werden berechnet...", 60)
        t0 = time.monotonic()
        render_instructions = self._stage_6_layout(filled_slides)
        logger.info(f"[Timing] Stage 6 (layout): {time.monotonic() - t0:.1f}s")

        # ── Stage 7: PPTX Rendering ──
        self._progress("stage_7", "PPTX wird gerendert...", 70)
        t0 = time.monotonic()
        pptx_path = self.renderer.render(
            render_instructions, output_dir=output_dir,
            progress_callback=self._progress_cb,
        )
        logger.info(f"[Timing] Stage 7 (render): {time.monotonic() - t0:.1f}s")

        # ── Stage 8: Visual Design Review ──
        self._progress("stage_8", "Design-Review...", 90)
        t0 = time.monotonic()
        design_result = await self._stage_8_design_review(
            pptx_path, render_instructions, output_dir,
        )
        if design_result and design_result.total_fixes_applied > 0:
            # Update pptx_path to the re-rendered version
            re_rendered = Path(output_dir or pptx_path.parent) / "presentation_v2.pptx"
            if re_rendered.exists():
                pptx_path = re_rendered
        logger.info(f"[Timing] Stage 8 (design review): {time.monotonic() - t0:.1f}s")

        final_quality = self._stage_8_quality_report(
            filled_slides, plan, quality, design_result,
        )

        total = time.monotonic() - pipeline_start
        logger.info(f"[Timing] TOTAL pipeline: {total:.1f}s ({len(plan.slides)} slides)")
        self._progress("done", f"Praesentation erstellt! ({total:.0f}s)", 100)

        return PipelineResult(
            pptx_path=pptx_path,
            plan=plan,
            filled_slides=filled_slides,
            quality=final_quality,
        )

    # ── Stage implementations ──

    async def _stage_1_interpret(self, user_input: str,
                                  document_text: str) -> InterpretedBriefing:
        from app.prompts.interpreter_prompt import build_interpreter_prompt
        from app.pipeline.llm_client import call_llm_structured_async

        prompt = build_interpreter_prompt(user_input, document_text)
        try:
            return await call_llm_structured_async(prompt, InterpretedBriefing, temperature=0.3, max_tokens=2048)
        except Exception as exc:
            logger.warning(f"Stage 1 LLM failed, using fallback: {exc}")
            return InterpretedBriefing(
                topic=user_input[:200],
                goal=f"Praesentation zu: {user_input[:100]}",
                audience=self.audience,
                image_style=self.image_style,
                requested_slide_count=10,
                content_themes=["general"],
            )

    async def _stage_2_storyline(self, briefing: InterpretedBriefing) -> Storyline:
        from app.prompts.storyline_prompt import build_storyline_prompt
        from app.pipeline.llm_client import call_llm_structured_async

        prompt = build_storyline_prompt(briefing.model_dump())
        try:
            storyline = await call_llm_structured_async(prompt, Storyline, temperature=0.5, max_tokens=4096)
            storyline.total_beats = len(storyline.beats)
            return storyline
        except Exception as exc:
            logger.warning(f"Stage 2 LLM failed, using fallback: {exc}")
            from app.schemas.models import StoryBeat, BeatType, EmotionalIntent, NarrativeArc
            return Storyline(
                narrative_arc=NarrativeArc.SITUATION_COMPLICATION_RESOLUTION,
                total_beats=briefing.requested_slide_count,
                beats=[
                    StoryBeat(position=1, beat_type=BeatType.OPENING,
                              core_message=briefing.topic,
                              content_theme="opening"),
                ] + [
                    StoryBeat(position=i+2, beat_type=BeatType.CONTEXT,
                              core_message=f"Punkt {i+1}",
                              content_theme="general")
                    for i in range(briefing.requested_slide_count - 2)
                ] + [
                    StoryBeat(position=briefing.requested_slide_count,
                              beat_type=BeatType.CLOSING,
                              core_message="Zusammenfassung und naechste Schritte",
                              content_theme="closing"),
                ],
            )

    async def _stage_3_slide_plan(self, storyline: Storyline,
                                   briefing: InterpretedBriefing) -> PresentationPlan:
        from app.prompts.slide_planner_prompt import build_slide_planner_prompt
        from app.prompts.profiles import AUDIENCE_PROFILES, IMAGE_STYLE_PROFILES
        from app.pipeline.llm_client import call_llm_structured_async

        # Build slide type catalog text
        from app.slide_types.registry import SLIDE_TYPE_REGISTRY
        catalog_lines = []
        for st, defn in SLIDE_TYPE_REGISTRY.items():
            catalog_lines.append(
                f"- {st.value}: {defn.purpose}. "
                f"Erlaubte Bloecke: {', '.join(defn.allowed_content_block_types) or 'keine'}. "
                f"Max {defn.max_total_chars} Zeichen."
            )
        catalog_text = "\n".join(catalog_lines)

        # Build transform rules text
        from app.slide_types.transforms import THEME_TO_SLIDE_TYPE
        transform_lines = []
        for theme, types in THEME_TO_SLIDE_TYPE.items():
            transform_lines.append(f"- {theme} -> {', '.join(t.value for t in types)}")
        transform_text = "\n".join(transform_lines)

        audience_profile = AUDIENCE_PROFILES.get(self.audience.value, "")
        image_profile = IMAGE_STYLE_PROFILES.get(self.image_style.value, "")

        prompt = build_slide_planner_prompt(
            storyline.model_dump(),
            briefing.model_dump(),
            catalog_text,
            transform_text,
            audience_profile,
            image_profile,
        )

        # Stage 3 produces large JSON — retry on parse failures
        last_exc = None
        for attempt in range(3):
            try:
                plan = await call_llm_structured_async(
                    prompt, PresentationPlan,
                    temperature=0.4 + (attempt * 0.1),
                    max_tokens=32768,
                )
                plan.audience = self.audience
                plan.image_style = self.image_style
                plan.metadata.total_slides = len(plan.slides)
                return plan
            except Exception as exc:
                last_exc = exc
                logger.warning(f"Stage 3 attempt {attempt + 1}/3 failed: {exc}")
                if attempt < 2:
                    self._progress("stage_3", f"Retry {attempt + 2}/3...", 22 + attempt * 3)
        logger.error(f"Stage 3 failed after 3 attempts: {last_exc}")
        raise last_exc

    async def _stage_4_validate(self, plan: PresentationPlan,
                                 storyline: Storyline,
                                 briefing: InterpretedBriefing) -> tuple[PresentationPlan, QualityReport]:
        from app.validators import validate_plan

        for attempt in range(MAX_REGEN_ATTEMPTS + 1):
            quality = validate_plan(plan)

            if quality.passed or attempt == MAX_REGEN_ATTEMPTS:
                return plan, quality

            # Collect failed slides with their errors
            failed_slides: list[tuple[int, list[str]]] = []
            for sf in quality.slide_findings:
                errors = [f.message for f in sf.findings if f.severity == "error"]
                warnings = [f.message for f in sf.findings if f.severity == "warning"]
                if errors:
                    failed_slides.append((sf.slide_index, errors + warnings))

            if not failed_slides:
                return plan, quality

            self._progress("stage_4", f"Regeneriere {len(failed_slides)} Folie(n)...", 35)

            # Apply auto-fixes first, then LLM regeneration for complex issues
            from app.validators.auto_fixes import apply_auto_fixes, needs_llm_regeneration

            llm_regen_tasks = []
            for idx, errors in failed_slides:
                if idx >= len(plan.slides):
                    continue
                plan.slides[idx] = apply_auto_fixes(plan.slides[idx])
                if needs_llm_regeneration(plan.slides[idx], errors):
                    llm_regen_tasks.append((idx, errors))

            # LLM-based regeneration for slides that can't be auto-fixed
            if llm_regen_tasks:
                self._progress("stage_4", f"LLM-Regenerierung fuer {len(llm_regen_tasks)} Folie(n)...", 37)
                regen_results = await asyncio.gather(*[
                    self._regenerate_slide(plan, idx, errors)
                    for idx, errors in llm_regen_tasks
                ])
                for (idx, _), result in zip(llm_regen_tasks, regen_results):
                    if result is not None:
                        plan.slides[idx] = result

        return plan, quality

    async def _regenerate_slide(self, plan: PresentationPlan,
                                 slide_idx: int,
                                 errors: list[str]) -> SlidePlan | None:
        """Use LLM to regenerate a single slide that failed validation."""
        from app.prompts.regenerator_prompt import build_regenerator_prompt
        from app.pipeline.llm_client import call_llm_structured_async

        slide = plan.slides[slide_idx]
        context_before = plan.slides[slide_idx - 1].model_dump() if slide_idx > 0 else None
        context_after = plan.slides[slide_idx + 1].model_dump() if slide_idx < len(plan.slides) - 1 else None

        prompt = build_regenerator_prompt(
            slide.model_dump(), errors, context_before, context_after,
        )

        try:
            regenerated = await call_llm_structured_async(prompt, SlidePlan, temperature=0.4)
            # Preserve position and beat_ref
            regenerated.position = slide.position
            regenerated.beat_ref = slide.beat_ref
            return regenerated
        except Exception as exc:
            logger.warning(f"LLM regeneration failed for slide {slide_idx + 1}: {exc}")
            return None

    def _stage_4b_compress(self, plan: PresentationPlan) -> list[CompressedSlideSpec]:
        """Compress all slides — semantic reduction, not truncation."""
        return compress_presentation(plan)

    def _stage_4c_quality_gate(
        self, slides: list[CompressedSlideSpec],
    ) -> tuple[list[CompressedSlideSpec], GateResult]:
        """Hard quality gate with replan loop.

        Score < 70 = BLOCK. Blocked slides go through the replan engine
        (reduce → switch layout → split → escalate) up to 3 attempts.
        """
        gate = QualityGate()
        replan = ReplanEngine()

        result = gate.evaluate(slides)
        if result.passed:
            return slides, result

        # Replan loop for blocked slides
        for attempt in range(3):
            if not result.blocked_slides:
                break

            self._progress(
                "stage_4c",
                f"Replan Versuch {attempt + 1}/3 "
                f"({result.blocked_count} Folien)...",
                39,
            )

            new_slides: list[CompressedSlideSpec] = []
            for i, slide in enumerate(slides):
                slide_result = result.slide_results[i] if i < len(result.slide_results) else None
                if slide_result and slide_result.blocked:
                    hint = replan.get_next_action(slide_result.replan_hint, attempt)
                    replanned = replan.replan_slide(slide, hint=hint, attempt=attempt)
                    new_slides.extend(replanned)
                else:
                    new_slides.append(slide)

            # Re-number positions
            for j, s in enumerate(new_slides):
                s.position = j + 1

            slides = new_slides
            result = gate.evaluate(slides)
            if result.passed:
                break

        return slides, result

    async def _stage_5_fill_content(self, plan: PresentationPlan) -> list[FilledSlide]:
        from app.prompts.content_filler_prompt import build_content_filler_prompt
        from app.prompts.profiles import AUDIENCE_PROFILES, IMAGE_STYLE_PROFILES
        from app.pipeline.llm_client import call_llm_structured_async

        audience_profile = AUDIENCE_PROFILES.get(self.audience.value, "")
        image_profile = IMAGE_STYLE_PROFILES.get(self.image_style.value, "")

        async def fill_one(slide_plan: SlidePlan) -> FilledSlide:
            prompt = build_content_filler_prompt(
                slide_plan.model_dump(),
                audience_profile,
                image_profile,
            )
            try:
                filled = await call_llm_structured_async(prompt, FilledSlide, temperature=0.5)
                filled.text_metrics = self._compute_metrics(filled)
                return filled
            except Exception as exc:
                logger.warning(f"Content fill failed for slide {slide_plan.position}: {exc}")
                return self._slide_plan_to_filled(slide_plan)

        # Run all content fills in parallel
        filled = await asyncio.gather(*[fill_one(sp) for sp in plan.slides])
        return list(filled)

    def _stage_6_layout(self, filled_slides: list[FilledSlide]) -> list[RenderInstruction]:
        instructions = []
        for i, slide in enumerate(filled_slides):
            instr = self.layout_engine.calculate(
                slide=slide,
                audience=self.audience,
                image_style=self.image_style,
                slide_index=i,
            )
            instructions.append(instr)
        return instructions

    async def _stage_8_design_review(
        self,
        pptx_path: Path,
        render_instructions: list[RenderInstruction],
        output_dir: str | None,
    ):
        """Run the visual design review agent on the rendered PPTX."""
        from app.services.design_review_agent import DesignReviewAgent, DesignReviewResult

        try:
            agent = DesignReviewAgent(
                render_instructions=render_instructions,
                renderer=self.renderer,
                max_iterations=2,
            )
            agent.set_progress_callback(self._progress_cb)
            result = await agent.review_and_fix(pptx_path, output_dir=output_dir)

            logger.info(
                f"[Pipeline] Design review: score={result.avg_score:.1f}, "
                f"fixes={result.total_fixes_applied}, passed={result.passed}"
            )
            return result

        except Exception as exc:
            logger.warning(f"[Pipeline] Design review failed (non-blocking): {exc}")
            return None

    def _stage_8_quality_report(
        self,
        filled_slides: list[FilledSlide],
        plan: PresentationPlan,
        validation_quality: QualityReport,
        design_result=None,
    ) -> QualityReport:
        """Combine validation quality with design review results."""
        # Merge design score into quality report if available
        if design_result is not None:
            validation_quality.design_score = design_result.avg_score
            validation_quality.design_fixes_applied = design_result.total_fixes_applied
        return validation_quality

    # ── Helpers ──

    def _compute_metrics(self, slide: FilledSlide) -> TextMetrics:
        total = len(slide.headline) + len(slide.subheadline)
        bullet_count = 0
        max_bullet_len = 0

        for cb in slide.content_blocks:
            if isinstance(cb, BulletsBlock):
                for item in cb.items:
                    bullet_count += 1
                    blen = len(item.text) + len(item.bold_prefix)
                    max_bullet_len = max(max_bullet_len, blen)
                    total += blen
            elif isinstance(cb, KpiBlock):
                total += len(cb.label) + len(cb.value) + len(cb.delta)
            elif isinstance(cb, TextBlock):
                total += len(cb.text)
            elif isinstance(cb, CardBlock):
                total += len(cb.title) + len(cb.body)
            elif isinstance(cb, QuoteBlock):
                total += len(cb.text) + len(cb.attribution)
            elif isinstance(cb, ComparisonColumnBlock):
                total += len(cb.column_label) + sum(len(i) for i in cb.items)
            elif isinstance(cb, TimelineEntryBlock):
                total += len(cb.date) + len(cb.title) + len(cb.description)
            elif isinstance(cb, ProcessStepBlock):
                total += len(cb.title) + len(cb.description)

        return TextMetrics(
            total_chars=total,
            bullet_count=bullet_count,
            max_bullet_length=max_bullet_len,
            headline_length=len(slide.headline),
        )

    def _slide_plan_to_filled(self, sp: SlidePlan) -> FilledSlide:
        """Convert a SlidePlan to a FilledSlide (fallback when content filler fails)."""
        filled = FilledSlide(
            position=sp.position,
            slide_type=sp.slide_type,
            headline=sp.headline,
            subheadline=sp.subheadline,
            core_message=sp.core_message,
            content_blocks=sp.content_blocks,
            visual=sp.visual,
            speaker_notes=sp.speaker_notes,
        )
        filled.text_metrics = self._compute_metrics(filled)
        return filled


class PipelineResult:
    """Result of a pipeline run."""

    def __init__(
        self,
        pptx_path: Path,
        plan: PresentationPlan,
        filled_slides: list[FilledSlide],
        quality: QualityReport,
    ):
        self.pptx_path = pptx_path
        self.plan = plan
        self.filled_slides = filled_slides
        self.quality = quality

    @property
    def passed(self) -> bool:
        return self.quality.passed

    @property
    def score(self) -> float:
        return self.quality.overall_score

    @property
    def slide_count(self) -> int:
        return len(self.filled_slides)
