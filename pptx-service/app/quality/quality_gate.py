"""Hard Quality Gate — score < 70 = BLOCK, not warning.

This replaces the V2 preflight's warning-only approach.
Slides that fail the gate are sent to the ReplanEngine for
controlled recovery (reduce content → switch layout → split → escalate).

The gate evaluates CompressedSlideSpecs against their LayoutBudget.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum

from app.domain.models import (
    CompressedSlideSpec,
    LayoutBudget,
    LAYOUT_BUDGETS,
    QualityScore,
    VisualRole,
)

logger = logging.getLogger(__name__)

PASS_THRESHOLD = 70.0
MAX_REPLAN_ATTEMPTS = 3


class GateVerdict(str, Enum):
    PASS = "pass"
    BLOCK = "block"


@dataclass
class SlideGateResult:
    """Result of quality gate evaluation for a single slide."""
    slide_index: int
    verdict: GateVerdict
    score: QualityScore
    violations: list[str] = field(default_factory=list)
    replan_hint: str = ""

    @property
    def passed(self) -> bool:
        return self.verdict == GateVerdict.PASS

    @property
    def blocked(self) -> bool:
        return self.verdict == GateVerdict.BLOCK


@dataclass
class GateResult:
    """Aggregated quality gate result for the entire presentation."""
    slide_results: list[SlideGateResult] = field(default_factory=list)
    overall_score: float = 100.0
    verdict: GateVerdict = GateVerdict.PASS

    @property
    def passed(self) -> bool:
        return self.verdict == GateVerdict.PASS

    @property
    def blocked_slides(self) -> list[int]:
        return [r.slide_index for r in self.slide_results if r.blocked]

    @property
    def blocked_count(self) -> int:
        return len(self.blocked_slides)


class QualityGate:
    """Evaluates compressed slides against hard quality constraints.

    Usage:
        gate = QualityGate()
        result = gate.evaluate(compressed_slides)
        if not result.passed:
            # Send blocked slides to ReplanEngine
            ...
    """

    def __init__(self, threshold: float = PASS_THRESHOLD):
        self.threshold = threshold

    def evaluate(self, slides: list[CompressedSlideSpec]) -> GateResult:
        """Evaluate all slides. Returns a GateResult with per-slide verdicts."""
        result = GateResult()
        total_score = 0.0

        for i, slide in enumerate(slides):
            slide_result = self._evaluate_slide(slide, i)
            result.slide_results.append(slide_result)
            total_score += slide_result.score.score

        if slides:
            result.overall_score = total_score / len(slides)
        result.verdict = (
            GateVerdict.PASS if result.overall_score >= self.threshold
            else GateVerdict.BLOCK
        )

        # Log results
        if result.blocked_count > 0:
            logger.warning(
                f"[QualityGate] BLOCKED: {result.blocked_count}/{len(slides)} slides "
                f"below {self.threshold}. Overall: {result.overall_score:.0f}/100"
            )
        else:
            logger.info(
                f"[QualityGate] PASSED: all {len(slides)} slides above threshold. "
                f"Overall: {result.overall_score:.0f}/100"
            )

        return result

    def _evaluate_slide(self, slide: CompressedSlideSpec, idx: int) -> SlideGateResult:
        """Score a single compressed slide against its budget."""
        budget = slide.budget
        violations = slide.exceeds_budget()

        # Compute dimension scores
        readability = self._score_readability(slide, budget)
        density = self._score_density(slide, budget)
        hierarchy = self._score_hierarchy(slide)
        balance = self._score_balance(slide)
        visual_fit = self._score_visual_fit(slide, budget)
        budget_compliance = self._score_budget_compliance(violations, budget)

        # Weighted total
        total = (
            readability * 0.20
            + density * 0.20
            + hierarchy * 0.15
            + balance * 0.10
            + visual_fit * 0.10
            + budget_compliance * 0.25
        )

        score = QualityScore(
            score=total,
            readability=readability,
            density=density,
            hierarchy=hierarchy,
            balance=balance,
            visual_fit=visual_fit,
            budget_compliance=budget_compliance,
            violations=violations,
        )

        verdict = GateVerdict.PASS if total >= self.threshold else GateVerdict.BLOCK
        replan_hint = self._suggest_replan(slide, violations, score) if verdict == GateVerdict.BLOCK else ""

        return SlideGateResult(
            slide_index=idx,
            verdict=verdict,
            score=score,
            violations=violations,
            replan_hint=replan_hint,
        )

    # ── Scoring dimensions ───────────────────────────────────────────────────

    def _score_readability(self, slide: CompressedSlideSpec, budget: LayoutBudget) -> float:
        """How readable is the slide? Based on text density vs budget."""
        total_chars = slide.compressed_char_count
        limit = budget.max_total_chars

        if total_chars == 0:
            return 85.0  # empty slides aren't unreadable, just sparse

        ratio = total_chars / limit
        if ratio <= 0.7:
            return 100.0
        if ratio <= 0.85:
            return 90.0
        if ratio <= 1.0:
            return 75.0
        if ratio <= 1.15:
            return 45.0
        return max(0, 25 - (ratio - 1.15) * 60)

    def _score_density(self, slide: CompressedSlideSpec, budget: LayoutBudget) -> float:
        """Content fill level — too empty or too full both score low."""
        total_chars = slide.compressed_char_count
        limit = budget.max_total_chars

        if limit == 0:
            return 100.0

        fill = total_chars / limit
        if 0.30 <= fill <= 0.70:
            return 100.0
        if 0.20 <= fill < 0.30 or 0.70 < fill <= 0.85:
            return 85.0
        if fill < 0.20:
            return max(45, 65 - (0.20 - fill) * 200)
        return max(15, 55 - (fill - 0.85) * 150)

    def _score_hierarchy(self, slide: CompressedSlideSpec) -> float:
        """Headline quality — is there a clear, statement-like headline?"""
        h = slide.headline.strip()
        if not h:
            return 25.0

        score = 100.0
        words = len(h.split())
        if words < 3:
            score -= 25  # too vague
        if words > 10:
            score -= 15  # too wordy
        if len(h) > 70:
            score -= 20

        # Penalize generic headlines
        generic = {"einleitung", "uebersicht", "zusammenfassung", "agenda",
                    "introduction", "overview", "summary", "next steps"}
        if h.lower() in generic:
            score -= 20

        return max(0, score)

    def _score_balance(self, slide: CompressedSlideSpec) -> float:
        """Are elements roughly equal in size?"""
        if len(slide.elements) < 2:
            return 100.0

        sizes = []
        for elem in slide.elements:
            sizes.append(sum(len(str(v)) for v in elem.values()))

        if not sizes:
            return 100.0

        min_s, max_s = min(sizes), max(sizes)
        if min_s == 0:
            return 35.0

        ratio = max_s / min_s
        if ratio <= 1.5:
            return 100.0
        if ratio <= 2.0:
            return 80.0
        if ratio <= 3.0:
            return 55.0
        return max(20, 40 - (ratio - 3.0) * 10)

    def _score_visual_fit(self, slide: CompressedSlideSpec, budget: LayoutBudget) -> float:
        """Does the slide have the right visual for its family?"""
        if budget.visual_role == VisualRole.NONE:
            return 100.0  # no visual expected

        if slide.visual_role == VisualRole.NONE and budget.visual_role != VisualRole.NONE:
            return 50.0  # expected visual but none provided

        if slide.visual_role == budget.visual_role:
            return 100.0

        return 75.0  # has a visual, just not the ideal type

    def _score_budget_compliance(self, violations: list[str], budget: LayoutBudget) -> float:
        """How well does the slide comply with its budget constraints?"""
        if not violations:
            return 100.0

        # Each violation costs 15 points
        penalty = len(violations) * 15
        return max(0, 100 - penalty)

    # ── Replan suggestion ────────────────────────────────────────────────────

    def _suggest_replan(self, slide: CompressedSlideSpec,
                        violations: list[str], score: QualityScore) -> str:
        """Suggest a replan strategy based on what failed."""
        if score.budget_compliance < 40:
            if any("total_chars" in v for v in violations):
                return "reduce_content"
            if any("elements" in v for v in violations):
                return "split_slide"
            if any("bullets" in v for v in violations):
                return "reduce_bullets"

        if score.density < 40:
            return "switch_layout"

        if score.readability < 40:
            return "reduce_content"

        if score.visual_fit < 40:
            return "add_visual"

        return "reduce_content"  # default
