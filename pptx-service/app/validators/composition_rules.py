"""Composition rules (C001-C007) — pre-render visual quality enforcement.

These rules go beyond structural correctness (slide_rules) and enforce
visual composition quality: balance, density, hierarchy, asset coverage.
"""

from __future__ import annotations

from app.design_tokens import DEFAULT_TOKENS
from app.schemas.models import (
    BulletsBlock, CardBlock, ComparisonColumnBlock, ImageRole,
    KpiBlock, ProcessStepBlock, QualityFinding, SlidePlan, SlideType,
    TimelineEntryBlock,
)

_tokens = DEFAULT_TOKENS
_comp = _tokens.composition
_spacing = _tokens.spacing


# ── helpers ───────────────────────────────────────────────────────────────────

def _block_text_len(block) -> int:
    """Approximate text length of a content block."""
    if isinstance(block, BulletsBlock):
        return sum(len(b.text) + len(b.bold_prefix) for b in block.items)
    if isinstance(block, CardBlock):
        return len(block.title) + len(block.body)
    if isinstance(block, KpiBlock):
        return len(block.label) + len(block.value) + len(block.delta)
    if isinstance(block, ComparisonColumnBlock):
        return len(block.column_label) + sum(len(i) for i in block.items)
    if isinstance(block, TimelineEntryBlock):
        return len(block.date) + len(block.title) + len(block.description)
    if isinstance(block, ProcessStepBlock):
        return len(block.title) + len(block.description)
    if hasattr(block, "text"):
        return len(block.text)
    return 0


def _total_slide_chars(slide: SlidePlan) -> int:
    total = len(slide.headline) + len(slide.subheadline) + len(slide.core_message)
    for block in slide.content_blocks:
        total += _block_text_len(block)
    return total


def _content_area_cm2() -> float:
    """Approximate usable content area in cm²."""
    w = _spacing.content_width
    h = _spacing.slide_height - _spacing.body_top - 1.0  # bottom margin
    return w * h


def _has_visual(slide: SlidePlan) -> bool:
    """Check if slide has image or chart."""
    if slide.visual and slide.visual.image_role != ImageRole.NONE:
        return True
    if slide.visual and slide.visual.chart_spec:
        return True
    return False


# ── rules ─────────────────────────────────────────────────────────────────────

def c001_visual_text_ratio(slide: SlidePlan, idx: int) -> list[QualityFinding]:
    """Slides with images/charts should have reduced text to avoid overcrowding."""
    if not _has_visual(slide):
        return []

    # Types where visual is the primary element — skip text ratio check
    if slide.slide_type in (SlideType.IMAGE_FULLBLEED, SlideType.CHART_INSIGHT):
        return []

    from app.validators.slide_rules import MAX_CHARS
    base_limit = MAX_CHARS.get(slide.slide_type, 300)
    reduced_limit = int(base_limit * _comp.visual_slide_text_reduction)
    total = _total_slide_chars(slide)

    if total > reduced_limit:
        return [QualityFinding(
            rule="C001", severity="warning",
            message=(
                f"Slide {idx + 1}: {total} chars with visual element exceeds "
                f"reduced limit ({reduced_limit}). Reduce text for visual breathing room."
            ),
            slide_index=idx,
        )]
    return []


def c002_content_density(slide: SlidePlan, idx: int) -> list[QualityFinding]:
    """Content characters per cm² must not exceed threshold."""
    # Skip minimal-content types
    if slide.slide_type in (
        SlideType.TITLE_HERO, SlideType.SECTION_DIVIDER,
        SlideType.IMAGE_FULLBLEED, SlideType.KEY_STATEMENT,
    ):
        return []

    total = _total_slide_chars(slide)
    area = _content_area_cm2()
    density = total / area if area > 0 else 0

    if density > _comp.max_chars_per_cm2:
        return [QualityFinding(
            rule="C002", severity="warning",
            message=(
                f"Slide {idx + 1}: content density {density:.1f} chars/cm² "
                f"exceeds maximum {_comp.max_chars_per_cm2}. Slide will feel cramped."
            ),
            slide_index=idx,
        )]
    return []


def c003_card_balance(slide: SlidePlan, idx: int) -> list[QualityFinding]:
    """Cards/KPIs within a slide should have similar text length for visual balance."""
    if slide.slide_type == SlideType.THREE_CARDS:
        cards = [b for b in slide.content_blocks if isinstance(b, CardBlock)]
        if len(cards) >= 2:
            lengths = [len(c.body) for c in cards]
            if min(lengths) > 0:
                ratio = max(lengths) / min(lengths)
                if ratio > _comp.max_card_length_deviation:
                    return [QualityFinding(
                        rule="C003", severity="warning",
                        message=(
                            f"Slide {idx + 1}: card body lengths are unbalanced "
                            f"(ratio {ratio:.1f}x). Aim for similar length across cards."
                        ),
                        slide_index=idx,
                    )]

    if slide.slide_type == SlideType.KPI_DASHBOARD:
        kpis = [b for b in slide.content_blocks if isinstance(b, KpiBlock)]
        if len(kpis) >= 2:
            label_lens = [len(k.label) for k in kpis]
            if min(label_lens) > 0:
                ratio = max(label_lens) / min(label_lens)
                if ratio > _comp.max_card_length_deviation:
                    return [QualityFinding(
                        rule="C003", severity="warning",
                        message=(
                            f"Slide {idx + 1}: KPI label lengths are unbalanced "
                            f"(ratio {ratio:.1f}x). Balance labels for visual symmetry."
                        ),
                        slide_index=idx,
                    )]
    return []


def c004_comparison_balance(slide: SlidePlan, idx: int) -> list[QualityFinding]:
    """Comparison columns should have similar text volume."""
    if slide.slide_type != SlideType.COMPARISON:
        return []

    cols = [b for b in slide.content_blocks if isinstance(b, ComparisonColumnBlock)]
    if len(cols) < 2:
        return []

    lengths = [sum(len(i) for i in c.items) for c in cols]
    if min(lengths) > 0:
        ratio = max(lengths) / min(lengths)
        if ratio > _comp.max_card_length_deviation:
            return [QualityFinding(
                rule="C004", severity="warning",
                message=(
                    f"Slide {idx + 1}: comparison columns are unbalanced "
                    f"(ratio {ratio:.1f}x). Balance content across columns."
                ),
                slide_index=idx,
            )]
    return []


def c005_process_step_consistency(slide: SlidePlan, idx: int) -> list[QualityFinding]:
    """Process steps should have consistent description lengths."""
    if slide.slide_type != SlideType.PROCESS_FLOW:
        return []

    steps = [b for b in slide.content_blocks if isinstance(b, ProcessStepBlock)]
    if len(steps) < 2:
        return []

    desc_lens = [len(s.description) for s in steps]
    if min(desc_lens) > 0:
        ratio = max(desc_lens) / min(desc_lens)
        if ratio > 2.5:
            return [QualityFinding(
                rule="C005", severity="warning",
                message=(
                    f"Slide {idx + 1}: process step descriptions vary widely "
                    f"(ratio {ratio:.1f}x). Keep step detail levels consistent."
                ),
                slide_index=idx,
            )]
    return []


def c006_visual_asset_required(slide: SlidePlan, idx: int) -> list[QualityFinding]:
    """Types that rely on visuals must actually have a visual asset configured."""
    visual_types = {
        SlideType.IMAGE_TEXT_SPLIT: "image",
        SlideType.IMAGE_FULLBLEED: "image",
        SlideType.CHART_INSIGHT: "chart",
    }

    required = visual_types.get(slide.slide_type)
    if not required:
        return []

    if required == "image":
        if not slide.visual or slide.visual.image_role == ImageRole.NONE:
            return [QualityFinding(
                rule="C006", severity="error",
                message=(
                    f"Slide {idx + 1}: {slide.slide_type.value} requires an image "
                    f"but no image is configured."
                ),
                slide_index=idx,
            )]
        if not slide.visual.image_description or len(slide.visual.image_description) < 10:
            return [QualityFinding(
                rule="C006", severity="error",
                message=(
                    f"Slide {idx + 1}: image_description is too vague for generation. "
                    f"Provide a detailed, specific description (min 10 chars)."
                ),
                slide_index=idx,
            )]

    if required == "chart":
        if not slide.visual or not slide.visual.chart_spec:
            return [QualityFinding(
                rule="C006", severity="error",
                message=(
                    f"Slide {idx + 1}: chart_insight requires a chart_spec "
                    f"but none is configured."
                ),
                slide_index=idx,
            )]

    return []


def c007_timeline_progression(slide: SlidePlan, idx: int) -> list[QualityFinding]:
    """Timeline entries should show clear temporal progression."""
    if slide.slide_type != SlideType.TIMELINE:
        return []

    entries = [b for b in slide.content_blocks if isinstance(b, TimelineEntryBlock)]
    if len(entries) < 3:
        return []

    # Check that dates aren't all identical
    dates = [e.date.strip() for e in entries]
    if len(set(dates)) == 1:
        return [QualityFinding(
            rule="C007", severity="warning",
            message=(
                f"Slide {idx + 1}: all timeline entries have the same date. "
                f"Timeline should show temporal progression."
            ),
            slide_index=idx,
        )]
    return []


# ── main entry point ──────────────────────────────────────────────────────────

_ALL_COMPOSITION_CHECKS = [
    c001_visual_text_ratio,
    c002_content_density,
    c003_card_balance,
    c004_comparison_balance,
    c005_process_step_consistency,
    c006_visual_asset_required,
    c007_timeline_progression,
]


def validate_composition(slide: SlidePlan, slide_index: int) -> list[QualityFinding]:
    """Run all composition rules and return findings."""
    findings: list[QualityFinding] = []
    for check in _ALL_COMPOSITION_CHECKS:
        findings.extend(check(slide, slide_index))
    return findings
