"""Slide-level validation rules (S001-S018)."""

from __future__ import annotations

from app.schemas.models import (
    BulletsBlock,
    ContentBlock,
    ImageRole,
    KpiBlock,
    QualityFinding,
    SlidePlan,
    SlideType,
    TimelineEntryBlock,
)

# ---- constants ----------------------------------------------------------------

MAX_CHARS: dict[SlideType, int] = {
    SlideType.TITLE_HERO: 130,
    SlideType.SECTION_DIVIDER: 100,
    SlideType.KEY_STATEMENT: 150,
    SlideType.BULLETS_FOCUSED: 250,
    SlideType.THREE_CARDS: 400,
    SlideType.KPI_DASHBOARD: 300,
    SlideType.IMAGE_TEXT_SPLIT: 250,
    SlideType.COMPARISON: 350,
    SlideType.TIMELINE: 500,
    SlideType.PROCESS_FLOW: 450,
    SlideType.CHART_INSIGHT: 200,
    SlideType.IMAGE_FULLBLEED: 60,
    SlideType.AGENDA: 280,
    SlideType.CLOSING: 250,
}

MAX_HEADLINE_LEN = 70
MAX_BULLET_LEN = 80

_BULLET_LIMITS: dict[SlideType, int] = {
    SlideType.BULLETS_FOCUSED: 3,
    SlideType.CHART_INSIGHT: 2,
    SlideType.CLOSING: 3,
}

_GENERIC_HEADLINES: set[str] = {
    "ueberblick", "überblick", "zusammenfassung", "einleitung", "agenda",
    "overview", "summary", "introduction",
}

# Map slide types to the content block types they allow.
_ALLOWED_BLOCK_TYPES: dict[SlideType, set[str]] = {
    SlideType.TITLE_HERO: {"text"},
    SlideType.SECTION_DIVIDER: {"text"},
    SlideType.KEY_STATEMENT: {"text", "quote"},
    SlideType.BULLETS_FOCUSED: {"bullets", "text"},
    SlideType.THREE_CARDS: {"card"},
    SlideType.KPI_DASHBOARD: {"kpi", "label_value"},
    SlideType.IMAGE_TEXT_SPLIT: {"bullets", "text"},
    SlideType.COMPARISON: {"comparison_column", "bullets", "text"},
    SlideType.TIMELINE: {"timeline_entry"},
    SlideType.PROCESS_FLOW: {"process_step"},
    SlideType.CHART_INSIGHT: {"bullets", "text"},
    SlideType.IMAGE_FULLBLEED: {"text"},
    SlideType.AGENDA: {"bullets", "text"},
    SlideType.CLOSING: {"bullets", "text", "quote"},
}


# ---- helpers ------------------------------------------------------------------

def _total_chars(slide: SlidePlan) -> int:
    """Rough count of all visible text characters on a slide."""
    total = len(slide.headline) + len(slide.subheadline) + len(slide.core_message)
    for block in slide.content_blocks:
        total += _block_chars(block)
    return total


def _block_chars(block: ContentBlock) -> int:  # type: ignore[arg-type]
    if hasattr(block, "items"):
        # BulletsBlock or ComparisonColumnBlock
        if isinstance(block, BulletsBlock):
            return sum(len(b.text) + len(b.bold_prefix) for b in block.items)
        return sum(len(str(i)) for i in block.items)  # type: ignore[union-attr]
    if hasattr(block, "text"):
        return len(block.text)  # type: ignore[union-attr]
    if hasattr(block, "value"):
        return len(getattr(block, "label", "")) + len(block.value)  # type: ignore[union-attr]
    if hasattr(block, "pairs"):
        return sum(len(p.label) + len(p.value) for p in block.pairs)  # type: ignore[union-attr]
    if hasattr(block, "title"):
        return len(block.title) + len(getattr(block, "description", ""))  # type: ignore[union-attr]
    return 0


# ---- individual rules --------------------------------------------------------

def s001_headline_required(slide: SlidePlan, idx: int) -> list[QualityFinding]:
    if not slide.headline or not slide.headline.strip():
        return [QualityFinding(
            rule="S001", severity="error",
            message=f"Slide {idx + 1}: headline is required.",
            slide_index=idx,
        )]
    return []


def s002_headline_max_length(slide: SlidePlan, idx: int) -> list[QualityFinding]:
    if len(slide.headline) > MAX_HEADLINE_LEN:
        return [QualityFinding(
            rule="S002", severity="error",
            message=f"Slide {idx + 1}: headline exceeds {MAX_HEADLINE_LEN} chars ({len(slide.headline)}).",
            auto_fixable=True, slide_index=idx,
        )]
    return []


def s003_core_message_required(slide: SlidePlan, idx: int) -> list[QualityFinding]:
    if not slide.core_message or not slide.core_message.strip():
        severity: str = (
            "warning"
            if slide.slide_type in (SlideType.TITLE_HERO, SlideType.SECTION_DIVIDER)
            else "error"
        )
        return [QualityFinding(
            rule="S003", severity=severity,  # type: ignore[arg-type]
            message=f"Slide {idx + 1}: core_message is missing.",
            slide_index=idx,
        )]
    return []


def s004_valid_slide_type(slide: SlidePlan, idx: int) -> list[QualityFinding]:
    try:
        SlideType(slide.slide_type)
    except ValueError:
        return [QualityFinding(
            rule="S004", severity="error",
            message=f"Slide {idx + 1}: invalid slide_type '{slide.slide_type}'.",
            slide_index=idx,
        )]
    return []


def s005_bullets_max_count(slide: SlidePlan, idx: int) -> list[QualityFinding]:
    max_count = _BULLET_LIMITS.get(slide.slide_type)
    if max_count is None:
        return []
    for block in slide.content_blocks:
        if isinstance(block, BulletsBlock) and len(block.items) > max_count:
            return [QualityFinding(
                rule="S005", severity="error",
                message=(
                    f"Slide {idx + 1}: {len(block.items)} bullets exceed "
                    f"max {max_count} for {slide.slide_type.value}."
                ),
                auto_fixable=True, slide_index=idx,
            )]
    return []


def s006_bullet_max_length(slide: SlidePlan, idx: int) -> list[QualityFinding]:
    findings: list[QualityFinding] = []
    for block in slide.content_blocks:
        if isinstance(block, BulletsBlock):
            for bi, item in enumerate(block.items):
                if len(item.text) > MAX_BULLET_LEN:
                    findings.append(QualityFinding(
                        rule="S006", severity="error",
                        message=(
                            f"Slide {idx + 1}, bullet {bi + 1}: "
                            f"text exceeds {MAX_BULLET_LEN} chars ({len(item.text)})."
                        ),
                        auto_fixable=True, slide_index=idx,
                    ))
    return findings


def s007_no_generic_headline(slide: SlidePlan, idx: int) -> list[QualityFinding]:
    if slide.slide_type == SlideType.AGENDA:
        return []
    if slide.headline.strip().lower() in _GENERIC_HEADLINES:
        return [QualityFinding(
            rule="S007", severity="warning",
            message=f"Slide {idx + 1}: headline '{slide.headline}' is too generic.",
            slide_index=idx,
        )]
    return []


def s008_content_blocks_match_type(slide: SlidePlan, idx: int) -> list[QualityFinding]:
    allowed = _ALLOWED_BLOCK_TYPES.get(slide.slide_type)
    if allowed is None:
        return []
    findings: list[QualityFinding] = []
    for block in slide.content_blocks:
        if block.type not in allowed:  # type: ignore[union-attr]
            findings.append(QualityFinding(
                rule="S008", severity="error",
                message=(
                    f"Slide {idx + 1}: content block type '{block.type}' "  # type: ignore[union-attr]
                    f"not allowed for slide type '{slide.slide_type.value}'."
                ),
                slide_index=idx,
            ))
    return findings


def s009_visual_role_valid(slide: SlidePlan, idx: int) -> list[QualityFinding]:
    if (
        slide.visual.image_role == ImageRole.DECORATIVE
        and slide.slide_type != SlideType.IMAGE_FULLBLEED
    ):
        return [QualityFinding(
            rule="S009", severity="warning",
            message=(
                f"Slide {idx + 1}: decorative images are only intended "
                f"for image_fullbleed slides."
            ),
            slide_index=idx,
        )]
    return []


def s010_total_text_density(slide: SlidePlan, idx: int) -> list[QualityFinding]:
    limit = MAX_CHARS.get(slide.slide_type, 300)
    total = _total_chars(slide)
    if total > limit:
        return [QualityFinding(
            rule="S010", severity="error",
            message=(
                f"Slide {idx + 1}: total text ({total} chars) exceeds "
                f"limit ({limit}) for {slide.slide_type.value}."
            ),
            auto_fixable=True, slide_index=idx,
        )]
    return []


def s011_kpi_has_value(slide: SlidePlan, idx: int) -> list[QualityFinding]:
    findings: list[QualityFinding] = []
    for block in slide.content_blocks:
        if isinstance(block, KpiBlock) and not block.value.strip():
            findings.append(QualityFinding(
                rule="S011", severity="error",
                message=f"Slide {idx + 1}: KPI block '{block.label}' has empty value.",
                slide_index=idx,
            ))
    return findings


def s012_timeline_min_entries(slide: SlidePlan, idx: int) -> list[QualityFinding]:
    if slide.slide_type != SlideType.TIMELINE:
        return []
    timeline_count = sum(
        1 for b in slide.content_blocks if isinstance(b, TimelineEntryBlock)
    )
    if timeline_count < 3:
        return [QualityFinding(
            rule="S012", severity="error",
            message=(
                f"Slide {idx + 1}: timeline has {timeline_count} entries, "
                f"minimum is 3."
            ),
            slide_index=idx,
        )]
    return []


def s013_speaker_notes_present(slide: SlidePlan, idx: int) -> list[QualityFinding]:
    if not slide.speaker_notes or not slide.speaker_notes.strip():
        return [QualityFinding(
            rule="S013", severity="warning",
            message=f"Slide {idx + 1}: speaker notes are missing.",
            slide_index=idx,
        )]
    return []


# Words that indicate a title is just a topic label, not a statement
_TOPIC_LABEL_PATTERNS: list[str] = [
    " und ", " & ", " im ", " in der ", " des ", " der ",
]

def s014_headline_is_statement(slide: SlidePlan, idx: int) -> list[QualityFinding]:
    """Headline must be a statement/assertion, not just a topic label."""
    if slide.slide_type in (SlideType.TITLE_HERO, SlideType.SECTION_DIVIDER, SlideType.AGENDA):
        return []
    headline = slide.headline.strip()
    if not headline:
        return []
    # A statement typically has a verb or is longer than 25 chars
    # A pure topic label is short and has no verb
    words = headline.split()
    if len(words) <= 3 and len(headline) < 30:
        return [QualityFinding(
            rule="S014", severity="warning",
            message=f"Slide {idx + 1}: headline '{headline}' appears to be a topic label, not a statement.",
            slide_index=idx,
        )]
    return []


_MIN_CONTENT_BLOCKS: dict[SlideType, int] = {
    SlideType.THREE_CARDS: 3,
    SlideType.KPI_DASHBOARD: 3,
    SlideType.TIMELINE: 4,
    SlideType.COMPARISON: 2,
    SlideType.PROCESS_FLOW: 3,
    SlideType.BULLETS_FOCUSED: 1,
    SlideType.IMAGE_TEXT_SPLIT: 1,
    SlideType.CLOSING: 1,
}

def s015_slide_type_fully_populated(slide: SlidePlan, idx: int) -> list[QualityFinding]:
    """Slide type must have minimum required content blocks."""
    min_blocks = _MIN_CONTENT_BLOCKS.get(slide.slide_type)
    if min_blocks is None:
        return []
    actual = len(slide.content_blocks)
    if actual < min_blocks:
        return [QualityFinding(
            rule="S015", severity="error",
            message=(
                f"Slide {idx + 1}: {slide.slide_type.value} has {actual} content block(s), "
                f"minimum is {min_blocks}. Slide appears underfilled."
            ),
            slide_index=idx,
        )]
    return []


def s016_image_has_function(slide: SlidePlan, idx: int) -> list[QualityFinding]:
    """Images must not be purely decorative (except on fullbleed slides)."""
    if slide.slide_type == SlideType.IMAGE_FULLBLEED:
        return []
    if not slide.visual or slide.visual.image_role == ImageRole.NONE:
        return []
    if slide.visual.image_role == ImageRole.DECORATIVE:
        return [QualityFinding(
            rule="S016", severity="error",
            message=(
                f"Slide {idx + 1}: image has role 'decorative'. "
                f"Every image must have a functional purpose (supporting, evidence, hero)."
            ),
            slide_index=idx,
        )]
    # Check image description quality
    desc = slide.visual.image_description or ""
    if slide.visual.image_role != ImageRole.NONE and len(desc) < 20:
        return [QualityFinding(
            rule="S016", severity="warning",
            message=f"Slide {idx + 1}: image_description is too short/vague ({len(desc)} chars).",
            slide_index=idx,
        )]
    return []


def s017_timeline_entries_complete(slide: SlidePlan, idx: int) -> list[QualityFinding]:
    """Timeline entries must have substantive descriptions."""
    if slide.slide_type != SlideType.TIMELINE:
        return []
    findings: list[QualityFinding] = []
    for block in slide.content_blocks:
        if isinstance(block, TimelineEntryBlock):
            if len(block.description) < 20:
                findings.append(QualityFinding(
                    rule="S017", severity="warning",
                    message=(
                        f"Slide {idx + 1}: timeline entry '{block.title}' has "
                        f"thin description ({len(block.description)} chars, min 20)."
                    ),
                    slide_index=idx,
                ))
    return findings


def s018_cards_have_body(slide: SlidePlan, idx: int) -> list[QualityFinding]:
    """Three_cards slides: each card must have substantive body text."""
    if slide.slide_type != SlideType.THREE_CARDS:
        return []
    from app.schemas.models import CardBlock
    findings: list[QualityFinding] = []
    for block in slide.content_blocks:
        if isinstance(block, CardBlock) and len(block.body) < 30:
            findings.append(QualityFinding(
                rule="S018", severity="warning",
                message=(
                    f"Slide {idx + 1}: card '{block.title}' has thin body "
                    f"({len(block.body)} chars, min 30)."
                ),
                slide_index=idx,
            ))
    return findings


# ---- main entry point ---------------------------------------------------------

_ALL_CHECKS = [
    s001_headline_required,
    s002_headline_max_length,
    s003_core_message_required,
    s004_valid_slide_type,
    s005_bullets_max_count,
    s006_bullet_max_length,
    s007_no_generic_headline,
    s008_content_blocks_match_type,
    s009_visual_role_valid,
    s010_total_text_density,
    s011_kpi_has_value,
    s012_timeline_min_entries,
    s013_speaker_notes_present,
    s014_headline_is_statement,
    s015_slide_type_fully_populated,
    s016_image_has_function,
    s017_timeline_entries_complete,
    s018_cards_have_body,
]


def validate_slide(slide: SlidePlan, slide_index: int) -> list[QualityFinding]:
    """Run all slide-level checks and return combined findings."""
    findings: list[QualityFinding] = []
    for check in _ALL_CHECKS:
        findings.extend(check(slide, slide_index))
    return findings
