"""Validators module -- validate a PresentationPlan and produce a QualityReport."""

from __future__ import annotations

from app.schemas.models import (
    PresentationPlan,
    QualityFinding,
    QualityReport,
    SlideFinding,
)

from .deck_rules import validate_deck
from .slide_rules import validate_slide
from .composition_rules import validate_composition
from .preflight import run_preflight

__all__ = ["validate_plan", "validate_slide", "validate_deck", "validate_composition", "run_preflight"]


def validate_plan(plan: PresentationPlan) -> QualityReport:
    """Run all slide-level and deck-level validations and return a scored report.

    Scoring:
        - Start at 100
        - Each ``error`` finding subtracts 15
        - Each ``warning`` finding subtracts 5
        - ``passed`` is ``True`` when the final score is >= 70
    """
    report = QualityReport()

    # -- slide-level checks ----------------------------------------------------
    for idx, slide in enumerate(plan.slides):
        slide_findings = validate_slide(slide, idx)
        # Composition rules (visual quality enforcement)
        slide_findings.extend(validate_composition(slide, idx))
        if slide_findings:
            report.slide_findings.append(
                SlideFinding(slide_index=idx, findings=slide_findings)
            )

    # -- deck-level checks -----------------------------------------------------
    deck_findings = validate_deck(plan)
    report.deck_findings.extend(deck_findings)

    # -- scoring ---------------------------------------------------------------
    all_findings: list[QualityFinding] = list(deck_findings)
    for sf in report.slide_findings:
        all_findings.extend(sf.findings)

    score = 100.0
    for finding in all_findings:
        if finding.severity == "error":
            score -= 15
        else:
            score -= 5

    report.overall_score = max(score, 0.0)
    report.passed = report.overall_score >= 70

    return report
