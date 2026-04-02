"""Preflight Quality Gate — scores slides before rendering.

Runs after Stage 4 (validation) and before Stage 5 (content fill).
Each slide gets a 0-100 score. Slides below threshold are flagged
for replanning or content reduction.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from app.design_tokens import DEFAULT_TOKENS
from app.schemas.models import (
    BulletsBlock, CardBlock, ComparisonColumnBlock, ImageRole,
    KpiBlock, PresentationPlan, ProcessStepBlock, QualityFinding,
    SlidePlan, SlideType, TimelineEntryBlock,
)
from app.validators.slide_rules import MAX_CHARS, _total_chars
from app.validators.composition_rules import (
    _block_text_len, _has_visual, _content_area_cm2,
)

logger = logging.getLogger(__name__)
_comp = DEFAULT_TOKENS.composition


@dataclass
class SlideScore:
    """Detailed score breakdown for a single slide."""
    slide_index: int
    readability: float = 100.0    # text density, bullet length
    balance: float = 100.0        # content block consistency
    density: float = 100.0        # overall fill level
    hierarchy: float = 100.0      # headline prominence
    visual_fit: float = 100.0     # visual asset appropriateness

    @property
    def total(self) -> float:
        weights = {
            "readability": 0.30,
            "balance": 0.15,
            "density": 0.25,
            "hierarchy": 0.15,
            "visual_fit": 0.15,
        }
        return (
            self.readability * weights["readability"]
            + self.balance * weights["balance"]
            + self.density * weights["density"]
            + self.hierarchy * weights["hierarchy"]
            + self.visual_fit * weights["visual_fit"]
        )

    @property
    def passed(self) -> bool:
        return self.total >= _comp.preflight_pass_score


@dataclass
class PreflightReport:
    """Aggregated preflight results for the entire deck."""
    slide_scores: list[SlideScore] = field(default_factory=list)
    findings: list[QualityFinding] = field(default_factory=list)

    @property
    def avg_score(self) -> float:
        if not self.slide_scores:
            return 100.0
        return sum(s.total for s in self.slide_scores) / len(self.slide_scores)

    @property
    def passed(self) -> bool:
        return self.avg_score >= _comp.preflight_pass_score

    @property
    def failing_slides(self) -> list[int]:
        return [s.slide_index for s in self.slide_scores if not s.passed]


# ── Scoring functions ─────────────────────────────────────────────────────────

def _score_readability(slide: SlidePlan) -> float:
    """Score 0-100 based on text density relative to limits."""
    limit = MAX_CHARS.get(slide.slide_type, 300)
    total = _total_chars(slide)

    if total == 0:
        return 90.0  # empty slides aren't a readability problem

    ratio = total / limit
    if ratio <= 0.7:
        return 100.0
    if ratio <= 0.9:
        return 90.0
    if ratio <= 1.0:
        return 75.0
    if ratio <= 1.2:
        return 50.0
    return max(0, 30 - (ratio - 1.2) * 50)


def _score_balance(slide: SlidePlan) -> float:
    """Score 0-100 based on content block consistency."""
    # Only applies to multi-element types
    blocks_with_text: list[int] = []

    if slide.slide_type == SlideType.THREE_CARDS:
        blocks_with_text = [len(b.body) for b in slide.content_blocks if isinstance(b, CardBlock)]
    elif slide.slide_type == SlideType.KPI_DASHBOARD:
        blocks_with_text = [len(b.label) for b in slide.content_blocks if isinstance(b, KpiBlock)]
    elif slide.slide_type == SlideType.COMPARISON:
        blocks_with_text = [
            sum(len(i) for i in b.items)
            for b in slide.content_blocks if isinstance(b, ComparisonColumnBlock)
        ]
    elif slide.slide_type == SlideType.PROCESS_FLOW:
        blocks_with_text = [
            len(b.description)
            for b in slide.content_blocks if isinstance(b, ProcessStepBlock)
        ]
    elif slide.slide_type == SlideType.TIMELINE:
        blocks_with_text = [
            len(b.description)
            for b in slide.content_blocks if isinstance(b, TimelineEntryBlock)
        ]

    if len(blocks_with_text) < 2:
        return 100.0

    min_len = min(blocks_with_text)
    max_len = max(blocks_with_text)
    if min_len == 0:
        return 40.0  # empty block is bad

    ratio = max_len / min_len
    if ratio <= 1.3:
        return 100.0
    if ratio <= 1.8:
        return 85.0
    if ratio <= 2.5:
        return 60.0
    return max(20, 50 - (ratio - 2.5) * 15)


def _score_density(slide: SlidePlan) -> float:
    """Score 0-100 based on overall content fill level.

    Too empty = wasted slide. Too full = unreadable.
    The sweet spot is 40-70% of the character limit.
    """
    limit = MAX_CHARS.get(slide.slide_type, 300)
    total = _total_chars(slide)

    if limit == 0:
        return 100.0

    fill = total / limit
    if 0.3 <= fill <= 0.75:
        return 100.0
    if 0.2 <= fill < 0.3 or 0.75 < fill <= 0.9:
        return 85.0
    if fill < 0.2:
        # Underfilled — might be wasteful but not terrible
        return max(50, 70 - (0.2 - fill) * 200)
    # Overfilled
    return max(20, 60 - (fill - 0.9) * 100)


def _score_hierarchy(slide: SlidePlan) -> float:
    """Score 0-100 based on headline quality and prominence."""
    headline = slide.headline.strip()
    if not headline:
        return 30.0

    score = 100.0

    # Headline shouldn't be too short (topic label)
    if len(headline) < 15:
        score -= 20

    # Headline shouldn't be too long
    if len(headline) > 70:
        score -= 15

    # Headline should be different from core_message
    if slide.core_message and headline.lower() == slide.core_message.lower():
        score -= 10

    return max(0, score)


def _score_visual_fit(slide: SlidePlan) -> float:
    """Score 0-100 based on visual asset appropriateness."""
    visual_required = slide.slide_type in (
        SlideType.IMAGE_TEXT_SPLIT, SlideType.IMAGE_FULLBLEED, SlideType.CHART_INSIGHT,
    )

    has_image = slide.visual and slide.visual.image_role != ImageRole.NONE
    has_chart = slide.visual and slide.visual.chart_spec is not None

    if visual_required:
        if slide.slide_type == SlideType.CHART_INSIGHT and not has_chart:
            return 30.0
        if slide.slide_type in (SlideType.IMAGE_TEXT_SPLIT, SlideType.IMAGE_FULLBLEED) and not has_image:
            return 30.0

        # Check description quality
        if has_image and slide.visual.image_description:
            desc_len = len(slide.visual.image_description)
            if desc_len < 20:
                return 60.0
            if desc_len < 40:
                return 80.0
        return 100.0

    # Non-visual types with images: slight bonus for well-placed visuals
    return 100.0


# ── Main entry point ──────────────────────────────────────────────────────────

def score_slide(slide: SlidePlan, idx: int) -> SlideScore:
    """Compute a detailed quality score for a single slide."""
    return SlideScore(
        slide_index=idx,
        readability=_score_readability(slide),
        balance=_score_balance(slide),
        density=_score_density(slide),
        hierarchy=_score_hierarchy(slide),
        visual_fit=_score_visual_fit(slide),
    )


def run_preflight(plan: PresentationPlan) -> PreflightReport:
    """Run the preflight quality gate on all slides.

    Returns a PreflightReport with per-slide scores and findings
    for any slides below the pass threshold.
    """
    report = PreflightReport()

    for idx, slide in enumerate(plan.slides):
        slide_score = score_slide(slide, idx)
        report.slide_scores.append(slide_score)

        if not slide_score.passed:
            details = []
            if slide_score.readability < 60:
                details.append(f"readability={slide_score.readability:.0f}")
            if slide_score.balance < 60:
                details.append(f"balance={slide_score.balance:.0f}")
            if slide_score.density < 60:
                details.append(f"density={slide_score.density:.0f}")
            if slide_score.hierarchy < 60:
                details.append(f"hierarchy={slide_score.hierarchy:.0f}")
            if slide_score.visual_fit < 60:
                details.append(f"visual_fit={slide_score.visual_fit:.0f}")

            report.findings.append(QualityFinding(
                rule="PREFLIGHT",
                severity="warning",
                message=(
                    f"Slide {idx + 1}: preflight score {slide_score.total:.0f}/100 "
                    f"(below {_comp.preflight_pass_score}). "
                    f"Weak areas: {', '.join(details) or 'general'}."
                ),
                slide_index=idx,
            ))

    if report.failing_slides:
        logger.warning(
            f"Preflight: {len(report.failing_slides)}/{len(plan.slides)} slides "
            f"below threshold. Avg score: {report.avg_score:.0f}"
        )
    else:
        logger.info(f"Preflight passed. Avg score: {report.avg_score:.0f}")

    return report
