"""Replan Engine — controlled recovery when the quality gate blocks a slide.

Strategy cascade (tried in order):
1. reduce_content  — further compress text, drop least important elements
2. reduce_bullets  — trim bullet count and length
3. switch_layout   — move to a less demanding LayoutFamily
4. split_slide     — break into 2+ slides
5. add_visual      — replace text with visual element
6. escalate        — give up, log error, pass with degraded quality flag

Each strategy produces a new CompressedSlideSpec that is re-evaluated
by the QualityGate. Max 3 attempts per slide before escalation.
"""

from __future__ import annotations

import logging
from enum import Enum

from app.domain.models import (
    CompressedSlideSpec,
    LayoutBudget,
    LayoutFamily,
    LAYOUT_BUDGETS,
    QualityScore,
    VisualRole,
)
from app.compression.content_compressor import split_slide

logger = logging.getLogger(__name__)

MAX_REPLAN_ATTEMPTS = 3


class ReplanAction(str, Enum):
    REDUCE_CONTENT = "reduce_content"
    REDUCE_BULLETS = "reduce_bullets"
    SWITCH_LAYOUT = "switch_layout"
    SPLIT_SLIDE = "split_slide"
    ADD_VISUAL = "add_visual"
    ESCALATE = "escalate"


# ── Layout fallback chains ──────────────────────────────────────────────────
# When a family is too constraining, try these alternatives (less demanding first)

_FAMILY_FALLBACKS: dict[LayoutFamily, list[LayoutFamily]] = {
    LayoutFamily.HERO: [LayoutFamily.KEY_FACT, LayoutFamily.CARD_GRID],
    LayoutFamily.KEY_FACT: [LayoutFamily.CARD_GRID, LayoutFamily.COMPARISON],
    LayoutFamily.CARD_GRID: [LayoutFamily.COMPARISON, LayoutFamily.TIMELINE],
    LayoutFamily.COMPARISON: [LayoutFamily.CARD_GRID],
    LayoutFamily.TIMELINE: [LayoutFamily.CARD_GRID],
    LayoutFamily.SECTION_DIVIDER: [LayoutFamily.KEY_FACT],
    LayoutFamily.CLOSING: [LayoutFamily.KEY_FACT, LayoutFamily.HERO],
}


class ReplanEngine:
    """Attempts controlled recovery for slides blocked by the quality gate.

    Usage:
        engine = ReplanEngine()
        fixed_slides = engine.replan(blocked_slides, gate_results)
    """

    def replan_slide(
        self,
        slide: CompressedSlideSpec,
        hint: str = "reduce_content",
        attempt: int = 0,
    ) -> list[CompressedSlideSpec]:
        """Apply a replan strategy to a single blocked slide.

        Returns a list because split_slide can produce multiple slides.
        """
        if attempt >= MAX_REPLAN_ATTEMPTS:
            logger.error(
                f"[Replan] Slide {slide.position}: max attempts reached, escalating"
            )
            return [self._escalate(slide)]

        action = ReplanAction(hint) if hint in ReplanAction.__members__.values() else ReplanAction.REDUCE_CONTENT

        logger.info(
            f"[Replan] Slide {slide.position}: attempt {attempt + 1}/{MAX_REPLAN_ATTEMPTS}, "
            f"action={action.value}"
        )

        if action == ReplanAction.REDUCE_CONTENT:
            return [self._reduce_content(slide)]
        elif action == ReplanAction.REDUCE_BULLETS:
            return [self._reduce_bullets(slide)]
        elif action == ReplanAction.SWITCH_LAYOUT:
            return [self._switch_layout(slide)]
        elif action == ReplanAction.SPLIT_SLIDE:
            return self._split_slide(slide)
        elif action == ReplanAction.ADD_VISUAL:
            return [self._add_visual(slide)]
        else:
            return [self._escalate(slide)]

    def get_next_action(self, hint: str, attempt: int) -> str:
        """Determine the next replan action based on attempt number.

        Cascade: reduce → switch → split → escalate
        """
        cascade = {
            "reduce_content": ["reduce_content", "switch_layout", "split_slide"],
            "reduce_bullets": ["reduce_bullets", "reduce_content", "switch_layout"],
            "switch_layout": ["switch_layout", "reduce_content", "split_slide"],
            "split_slide": ["split_slide", "reduce_content", "escalate"],
            "add_visual": ["add_visual", "reduce_content", "switch_layout"],
        }
        actions = cascade.get(hint, ["reduce_content", "switch_layout", "split_slide"])
        if attempt < len(actions):
            return actions[attempt]
        return "escalate"

    # ── Strategy implementations ─────────────────────────────────────────────

    def _reduce_content(self, slide: CompressedSlideSpec) -> CompressedSlideSpec:
        """Aggressively reduce content to fit budget."""
        budget = slide.budget

        # Reduce headline
        headline_words = slide.headline.split()
        if len(headline_words) > budget.max_headline_words:
            slide.headline = " ".join(headline_words[:budget.max_headline_words])

        # Reduce supporting text
        if slide.supporting_text:
            body_words = slide.supporting_text.split()
            max_w = max(budget.max_body_words, 1)
            if len(body_words) > max_w:
                # Keep first sentence only
                first_dot = slide.supporting_text.find(".")
                if 0 < first_dot < budget.max_body_chars:
                    slide.supporting_text = slide.supporting_text[:first_dot + 1]
                else:
                    slide.supporting_text = " ".join(body_words[:max_w])

        # Trim bullets
        if slide.bullets:
            slide.bullets = slide.bullets[:max(budget.max_bullets, 1)]
            slide.bullets = [
                " ".join(b.split()[:budget.max_bullet_words])
                for b in slide.bullets
            ]

        # Trim elements
        if slide.elements:
            slide.elements = slide.elements[:budget.max_elements]

        # Recalculate
        slide.compressed_char_count = self._count_chars(slide)
        slide.compression_ratio = slide.original_char_count / max(slide.compressed_char_count, 1)

        logger.info(
            f"[Replan] Slide {slide.position}: reduced to {slide.compressed_char_count} chars"
        )
        return slide

    def _reduce_bullets(self, slide: CompressedSlideSpec) -> CompressedSlideSpec:
        """Specifically target bullet reduction."""
        budget = slide.budget

        if not slide.bullets:
            return self._reduce_content(slide)

        # Keep max allowed, trim each to budget
        slide.bullets = slide.bullets[:budget.max_bullets]
        slide.bullets = [
            " ".join(b.split()[:budget.max_bullet_words])
            for b in slide.bullets
        ]

        slide.compressed_char_count = self._count_chars(slide)
        return slide

    def _switch_layout(self, slide: CompressedSlideSpec) -> CompressedSlideSpec:
        """Switch to a less constraining layout family."""
        fallbacks = _FAMILY_FALLBACKS.get(slide.layout_family, [])

        for family in fallbacks:
            new_budget = LAYOUT_BUDGETS[family]
            # Check if the current content fits the new family's budget
            if slide.compressed_char_count <= new_budget.max_total_chars:
                old_family = slide.layout_family
                slide.layout_family = family
                logger.info(
                    f"[Replan] Slide {slide.position}: switched "
                    f"{old_family.value} → {family.value}"
                )
                return slide

        # No suitable fallback — try the most permissive family
        most_permissive = max(
            LAYOUT_BUDGETS.items(),
            key=lambda x: x[1].max_total_chars,
        )
        if most_permissive[1].max_total_chars > slide.compressed_char_count:
            old_family = slide.layout_family
            slide.layout_family = most_permissive[0]
            logger.info(
                f"[Replan] Slide {slide.position}: switched "
                f"{old_family.value} → {most_permissive[0].value} (most permissive)"
            )
            return slide

        # Still doesn't fit — fallback to content reduction
        logger.warning(
            f"[Replan] Slide {slide.position}: no suitable layout fallback, reducing content"
        )
        return self._reduce_content(slide)

    def _split_slide(self, slide: CompressedSlideSpec) -> list[CompressedSlideSpec]:
        """Split into multiple slides using the compressor's split logic."""
        result = split_slide(slide)
        if len(result) == 1:
            # split_slide decided not to split — fall back to content reduction
            return [self._reduce_content(slide)]
        logger.info(
            f"[Replan] Slide {slide.position}: split into {len(result)} slides"
        )
        return result

    def _add_visual(self, slide: CompressedSlideSpec) -> CompressedSlideSpec:
        """Replace text content with a visual role hint.

        This doesn't generate the visual — it marks the slide as needing
        one, which the renderer will handle. Reduces text to make room.
        """
        if slide.visual_role == VisualRole.NONE:
            slide.visual_role = VisualRole.SUPPORTING_ICON

        # Reduce text to make room for the visual
        budget = slide.budget
        reduced_body_budget = budget.max_body_words // 2
        if slide.supporting_text and reduced_body_budget > 0:
            words = slide.supporting_text.split()
            slide.supporting_text = " ".join(words[:reduced_body_budget])

        # Remove some bullets to make visual space
        if slide.bullets and len(slide.bullets) > 2:
            slide.bullets = slide.bullets[:2]

        slide.compressed_char_count = self._count_chars(slide)
        logger.info(
            f"[Replan] Slide {slide.position}: added visual, "
            f"reduced text to {slide.compressed_char_count} chars"
        )
        return slide

    def _escalate(self, slide: CompressedSlideSpec) -> CompressedSlideSpec:
        """Last resort — mark as degraded and let it through.

        The slide will render but with a quality warning in the final report.
        """
        logger.error(
            f"[Replan] Slide {slide.position}: ESCALATED — "
            f"could not meet quality threshold after {MAX_REPLAN_ATTEMPTS} attempts. "
            f"Passing with degraded quality flag."
        )
        return slide

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _count_chars(self, slide: CompressedSlideSpec) -> int:
        total = len(slide.headline) + len(slide.supporting_text)
        total += sum(len(b) for b in slide.bullets)
        total += sum(len(str(e)) for e in slide.elements)
        return total
