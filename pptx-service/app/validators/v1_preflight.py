"""Preflight Quality Gate for V1 SlideContent model.

Mirrors preflight.py (V2) — scores each slide 0-100 before rendering.
Slides below threshold are logged as warnings. The pipeline continues
(no hard block) but the warnings feed into QA prioritization.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from app.models.schemas import SlideContent, PresentationData
from app.validators.v1_slide_rules import MAX_CHARS, _total_chars

logger = logging.getLogger(__name__)

PREFLIGHT_PASS_SCORE = 70


@dataclass
class V1SlideScore:
    """Detailed score breakdown for a single V1 slide."""
    slide_index: int
    readability: float = 100.0
    density: float = 100.0
    hierarchy: float = 100.0
    completeness: float = 100.0

    @property
    def total(self) -> float:
        weights = {
            "readability": 0.30,
            "density": 0.30,
            "hierarchy": 0.20,
            "completeness": 0.20,
        }
        return (
            self.readability * weights["readability"]
            + self.density * weights["density"]
            + self.hierarchy * weights["hierarchy"]
            + self.completeness * weights["completeness"]
        )

    @property
    def passed(self) -> bool:
        return self.total >= PREFLIGHT_PASS_SCORE


@dataclass
class V1PreflightReport:
    """Aggregated preflight results for the entire V1 deck."""
    slide_scores: list[V1SlideScore] = field(default_factory=list)

    @property
    def avg_score(self) -> float:
        if not self.slide_scores:
            return 100.0
        return sum(s.total for s in self.slide_scores) / len(self.slide_scores)

    @property
    def passed(self) -> bool:
        return self.avg_score >= PREFLIGHT_PASS_SCORE

    @property
    def failing_slides(self) -> list[int]:
        return [s.slide_index for s in self.slide_scores if not s.passed]


# ── Scoring functions ─────────────────────────────────────────────────────────

def _score_readability(slide: SlideContent) -> float:
    """Score 0-100 based on text density relative to limits."""
    limit = MAX_CHARS.get(slide.layout, 300)
    total = _total_chars(slide)

    if total == 0:
        return 90.0

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


def _score_density(slide: SlideContent) -> float:
    """Score 0-100 — sweet spot is 30-75% fill."""
    limit = MAX_CHARS.get(slide.layout, 300)
    total = _total_chars(slide)

    if limit == 0:
        return 100.0

    fill = total / limit
    if 0.3 <= fill <= 0.75:
        return 100.0
    if 0.2 <= fill < 0.3 or 0.75 < fill <= 0.9:
        return 85.0
    if fill < 0.2:
        return max(50, 70 - (0.2 - fill) * 200)
    return max(20, 60 - (fill - 0.9) * 100)


def _score_hierarchy(slide: SlideContent) -> float:
    """Score 0-100 based on headline quality."""
    headline = slide.title.strip()
    if not headline:
        if slide.layout in ("title", "section"):
            return 30.0
        return 60.0  # non-title slides without headline are less critical

    score = 100.0

    if len(headline) < 15:
        score -= 20
    if len(headline) > 70:
        score -= 15
    # Title duplicating subtitle is wasteful
    if slide.subtitle and headline.lower() == slide.subtitle.lower():
        score -= 10

    return max(0, score)


def _score_completeness(slide: SlideContent) -> float:
    """Score 0-100 — does the slide have the expected content for its layout?"""
    layout = slide.layout

    if layout == "title":
        if not slide.title.strip():
            return 30.0
        return 100.0

    if layout == "content":
        has_content = bool(slide.body.strip()) or bool(slide.bullets)
        return 100.0 if has_content else 40.0

    if layout == "two_column":
        has_left = bool(slide.left_column.strip())
        has_right = bool(slide.right_column.strip())
        if has_left and has_right:
            return 100.0
        if has_left or has_right:
            return 60.0
        return 30.0

    if layout == "image":
        has_desc = bool(slide.image_description) and len(slide.image_description) >= 10
        return 100.0 if has_desc else 50.0

    if layout == "chart":
        has_data = bool(slide.chart_data) and len(slide.chart_data.strip()) >= 5
        return 100.0 if has_data else 30.0

    return 90.0  # section, closing — minimal requirements


# ── Main entry point ──────────────────────────────────────────────────────────

def score_v1_slide(slide: SlideContent, idx: int) -> V1SlideScore:
    """Compute a quality score for a single V1 slide."""
    return V1SlideScore(
        slide_index=idx,
        readability=_score_readability(slide),
        density=_score_density(slide),
        hierarchy=_score_hierarchy(slide),
        completeness=_score_completeness(slide),
    )


def run_v1_preflight(data: PresentationData) -> V1PreflightReport:
    """Run the preflight quality gate on all V1 slides.

    Logs warnings for slides below threshold but does not block rendering.
    """
    report = V1PreflightReport()

    for idx, slide in enumerate(data.slides):
        slide_score = score_v1_slide(slide, idx)
        report.slide_scores.append(slide_score)

        if not slide_score.passed:
            weak = []
            if slide_score.readability < 60:
                weak.append(f"readability={slide_score.readability:.0f}")
            if slide_score.density < 60:
                weak.append(f"density={slide_score.density:.0f}")
            if slide_score.hierarchy < 60:
                weak.append(f"hierarchy={slide_score.hierarchy:.0f}")
            if slide_score.completeness < 60:
                weak.append(f"completeness={slide_score.completeness:.0f}")

            logger.warning(
                f"[V1 Preflight] Slide {idx + 1}: score {slide_score.total:.0f}/100 "
                f"(below {PREFLIGHT_PASS_SCORE}). Weak: {', '.join(weak) or 'general'}"
            )

    if report.failing_slides:
        logger.warning(
            f"[V1 Preflight] {len(report.failing_slides)}/{len(data.slides)} slides "
            f"below threshold. Avg score: {report.avg_score:.0f}"
        )
    else:
        logger.info(f"[V1 Preflight] All slides passed. Avg score: {report.avg_score:.0f}")

    return report
