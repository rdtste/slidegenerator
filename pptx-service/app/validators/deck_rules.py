"""Deck-level validation rules (D001-D013)."""

from __future__ import annotations

from app.schemas.models import PresentationPlan, QualityFinding, SlideType


# ---- individual rules --------------------------------------------------------

def d001_starts_with_title_hero(plan: PresentationPlan) -> list[QualityFinding]:
    if not plan.slides or plan.slides[0].slide_type != SlideType.TITLE_HERO:
        return [QualityFinding(
            rule="D001", severity="error",
            message="Deck must start with a title_hero slide.",
        )]
    return []


def d002_ends_with_closing(plan: PresentationPlan) -> list[QualityFinding]:
    if not plan.slides or plan.slides[-1].slide_type != SlideType.CLOSING:
        return [QualityFinding(
            rule="D002", severity="error",
            message="Deck must end with a closing slide.",
        )]
    return []


def d003_min_type_variety(plan: PresentationPlan) -> list[QualityFinding]:
    types = {s.slide_type for s in plan.slides}
    if len(types) < 3:
        return [QualityFinding(
            rule="D003", severity="error",
            message=f"Deck uses only {len(types)} slide type(s); at least 3 required.",
        )]
    return []


def d004_no_consecutive_bullets(plan: PresentationPlan) -> list[QualityFinding]:
    findings: list[QualityFinding] = []
    for i in range(1, len(plan.slides)):
        if (
            plan.slides[i].slide_type == SlideType.BULLETS_FOCUSED
            and plan.slides[i - 1].slide_type == SlideType.BULLETS_FOCUSED
        ):
            findings.append(QualityFinding(
                rule="D004", severity="error",
                message=f"Slides {i} and {i + 1}: consecutive bullets_focused not allowed.",
            ))
    return findings


def d005_no_3_same_type(plan: PresentationPlan) -> list[QualityFinding]:
    findings: list[QualityFinding] = []
    for i in range(2, len(plan.slides)):
        if (
            plan.slides[i].slide_type == plan.slides[i - 1].slide_type
            == plan.slides[i - 2].slide_type
        ):
            findings.append(QualityFinding(
                rule="D005", severity="warning",
                message=(
                    f"Slides {i - 1}-{i + 1}: three consecutive "
                    f"'{plan.slides[i].slide_type.value}' slides."
                ),
            ))
    return findings


def d006_slide_count_range(plan: PresentationPlan) -> list[QualityFinding]:
    count = len(plan.slides)
    if count < 5 or count > 25:
        return [QualityFinding(
            rule="D006", severity="error",
            message=f"Deck has {count} slides; must be between 5 and 25.",
        )]
    return []


def d007_max_key_statements(plan: PresentationPlan) -> list[QualityFinding]:
    ks_count = sum(1 for s in plan.slides if s.slide_type == SlideType.KEY_STATEMENT)
    if ks_count > 2:
        return [QualityFinding(
            rule="D007", severity="warning",
            message=f"Deck has {ks_count} key_statement slides; max recommended is 2.",
        )]
    return []


def d008_section_divider_not_at_end(plan: PresentationPlan) -> list[QualityFinding]:
    findings: list[QualityFinding] = []
    n = len(plan.slides)
    if n >= 1 and plan.slides[-1].slide_type == SlideType.SECTION_DIVIDER:
        findings.append(QualityFinding(
            rule="D008", severity="error",
            message="Section divider must not be the last slide.",
        ))
    if n >= 2 and plan.slides[-2].slide_type == SlideType.SECTION_DIVIDER:
        findings.append(QualityFinding(
            rule="D008", severity="error",
            message="Section divider must not be the second-to-last slide.",
        ))
    return findings


def d009_historical_needs_timeline(plan: PresentationPlan) -> list[QualityFinding]:
    """Historical/chronological decks must include at least one timeline slide."""
    # Detect historical theme from slides' content
    historical_indicators = {"geschichte", "history", "entwicklung", "evolution",
                            "jahrhundert", "century", "epoche", "epoch", "antike",
                            "mittelalter", "neuzeit", "industrialisierung", "chronolog"}
    all_text = " ".join(
        s.headline.lower() + " " + s.core_message.lower() + " " + s.subheadline.lower()
        for s in plan.slides
    ).lower()
    is_historical = any(ind in all_text for ind in historical_indicators)
    if not is_historical:
        return []
    has_timeline = any(s.slide_type == SlideType.TIMELINE for s in plan.slides)
    if not has_timeline:
        return [QualityFinding(
            rule="D009", severity="error",
            message="Historical/chronological deck must include at least one timeline slide.",
        )]
    return []


_LOW_CONTENT_TYPES = {SlideType.TITLE_HERO, SlideType.SECTION_DIVIDER, SlideType.KEY_STATEMENT}

def d010_max_low_content_slides(plan: PresentationPlan) -> list[QualityFinding]:
    """Max 3 low-content slides (title_hero + section_divider + key_statement) per deck."""
    low_count = sum(1 for s in plan.slides if s.slide_type in _LOW_CONTENT_TYPES)
    max_allowed = max(3, len(plan.slides) // 3)
    if low_count > max_allowed:
        return [QualityFinding(
            rule="D010", severity="warning",
            message=(
                f"Deck has {low_count} low-content slides "
                f"(title/section/key_statement), max {max_allowed} recommended."
            ),
        )]
    return []


def d011_no_consecutive_low_content(plan: PresentationPlan) -> list[QualityFinding]:
    """No more than 2 consecutive low-content slides."""
    findings: list[QualityFinding] = []
    run = 0
    for i, s in enumerate(plan.slides):
        if s.slide_type in _LOW_CONTENT_TYPES:
            run += 1
            if run > 2:
                findings.append(QualityFinding(
                    rule="D011", severity="error",
                    message=f"Slides {i - 1}-{i + 1}: more than 2 consecutive low-content slides.",
                ))
        else:
            run = 0
    return findings


def d012_closing_not_prose(plan: PresentationPlan) -> list[QualityFinding]:
    """Closing slide should have structured content (bullets/cards), not a text wall."""
    if not plan.slides:
        return []
    last = plan.slides[-1]
    if last.slide_type != SlideType.CLOSING:
        return []
    from app.schemas.models import TextBlock
    has_only_text = (
        len(last.content_blocks) == 1
        and isinstance(last.content_blocks[0], TextBlock)
        and len(last.content_blocks[0].text) > 150
    )
    if has_only_text:
        return [QualityFinding(
            rule="D012", severity="warning",
            message="Closing slide should use structured content (bullets/summary), not a long text block.",
        )]
    return []


def d013_dramaturgic_development(plan: PresentationPlan) -> list[QualityFinding]:
    """Deck should show development — not all slides with same semantic function."""
    if len(plan.slides) < 5:
        return []
    # Check that the middle slides aren't all the same type
    middle = plan.slides[1:-1]
    type_counts: dict[SlideType, int] = {}
    for s in middle:
        type_counts[s.slide_type] = type_counts.get(s.slide_type, 0) + 1
    dominant_count = max(type_counts.values()) if type_counts else 0
    if dominant_count > len(middle) * 0.6:
        dominant_type = max(type_counts, key=type_counts.get)
        return [QualityFinding(
            rule="D013", severity="warning",
            message=(
                f"Deck lacks dramaturgic variety: {dominant_count}/{len(middle)} "
                f"middle slides are '{dominant_type.value}'. Mix slide types for narrative tension."
            ),
        )]
    return []


# ---- main entry point ---------------------------------------------------------

_ALL_CHECKS = [
    d001_starts_with_title_hero,
    d002_ends_with_closing,
    d003_min_type_variety,
    d004_no_consecutive_bullets,
    d005_no_3_same_type,
    d006_slide_count_range,
    d007_max_key_statements,
    d008_section_divider_not_at_end,
    d009_historical_needs_timeline,
    d010_max_low_content_slides,
    d011_no_consecutive_low_content,
    d012_closing_not_prose,
    d013_dramaturgic_development,
]


def validate_deck(plan: PresentationPlan) -> list[QualityFinding]:
    """Run all deck-level checks and return combined findings."""
    findings: list[QualityFinding] = []
    for check in _ALL_CHECKS:
        findings.extend(check(plan))
    return findings
