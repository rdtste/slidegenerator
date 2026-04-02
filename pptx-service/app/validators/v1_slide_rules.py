"""Slide-level validation rules for V1 SlideContent model.

Mirrors the quality logic from slide_rules.py (V2) but operates on the
simpler V1 SlideContent model used by pptx_service.py / template-based generation.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from app.models.schemas import SlideContent, PresentationData

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

MAX_HEADLINE_LEN = 70
MAX_BULLET_LEN = 60

# Max total characters per layout type (adapted from V2 MAX_CHARS)
MAX_CHARS: dict[str, int] = {
    "title": 110,
    "section": 80,
    "content": 250,
    "two_column": 350,
    "image": 200,
    "chart": 170,
    "closing": 200,
}

# Max bullet count per layout
_BULLET_LIMITS: dict[str, int] = {
    "content": 6,
    "closing": 4,
    "chart": 3,
    "image": 4,
}

_GENERIC_HEADLINES: set[str] = {
    "ueberblick", "überblick", "zusammenfassung", "einleitung", "agenda",
    "overview", "summary", "introduction", "inhalt", "themen",
}


# ── Finding model ─────────────────────────────────────────────────────────────

@dataclass
class V1Finding:
    """A single quality finding for a V1 slide."""
    rule: str
    severity: str  # "error" | "warning"
    message: str
    slide_index: int
    auto_fixable: bool = False


# ── Helpers ───────────────────────────────────────────────────────────────────

def _total_chars(slide: SlideContent) -> int:
    """Approximate total visible text characters on a V1 slide."""
    total = len(slide.title) + len(slide.subtitle) + len(slide.body)
    total += sum(len(b) for b in slide.bullets)
    total += len(slide.left_column) + len(slide.right_column)
    return total


# ── Individual rules ──────────────────────────────────────────────────────────

def s001_headline_required(slide: SlideContent, idx: int) -> list[V1Finding]:
    if slide.layout == "title" and not slide.title.strip():
        return [V1Finding(
            rule="V1-S001", severity="error",
            message=f"Slide {idx + 1}: title slide has no headline.",
            slide_index=idx,
        )]
    return []


def s002_headline_max_length(slide: SlideContent, idx: int) -> list[V1Finding]:
    if len(slide.title) > MAX_HEADLINE_LEN:
        return [V1Finding(
            rule="V1-S002", severity="error",
            message=f"Slide {idx + 1}: title exceeds {MAX_HEADLINE_LEN} chars ({len(slide.title)}).",
            auto_fixable=True, slide_index=idx,
        )]
    return []


def s003_bullet_max_count(slide: SlideContent, idx: int) -> list[V1Finding]:
    max_count = _BULLET_LIMITS.get(slide.layout)
    if max_count is None:
        return []
    if len(slide.bullets) > max_count:
        return [V1Finding(
            rule="V1-S003", severity="error",
            message=(
                f"Slide {idx + 1}: {len(slide.bullets)} bullets exceed "
                f"max {max_count} for layout '{slide.layout}'."
            ),
            auto_fixable=True, slide_index=idx,
        )]
    return []


def s004_bullet_max_length(slide: SlideContent, idx: int) -> list[V1Finding]:
    findings: list[V1Finding] = []
    for bi, bullet in enumerate(slide.bullets):
        if len(bullet) > MAX_BULLET_LEN:
            findings.append(V1Finding(
                rule="V1-S004", severity="error",
                message=(
                    f"Slide {idx + 1}, bullet {bi + 1}: "
                    f"text exceeds {MAX_BULLET_LEN} chars ({len(bullet)})."
                ),
                auto_fixable=True, slide_index=idx,
            ))
    return findings


def s005_no_generic_headline(slide: SlideContent, idx: int) -> list[V1Finding]:
    if slide.layout in ("title", "section"):
        return []
    if slide.title.strip().lower() in _GENERIC_HEADLINES:
        return [V1Finding(
            rule="V1-S005", severity="warning",
            message=f"Slide {idx + 1}: title '{slide.title}' is too generic.",
            slide_index=idx,
        )]
    return []


def s006_total_text_density(slide: SlideContent, idx: int) -> list[V1Finding]:
    limit = MAX_CHARS.get(slide.layout, 300)
    total = _total_chars(slide)
    if total > limit:
        return [V1Finding(
            rule="V1-S006", severity="error",
            message=(
                f"Slide {idx + 1}: total text ({total} chars) exceeds "
                f"limit ({limit}) for layout '{slide.layout}'."
            ),
            auto_fixable=True, slide_index=idx,
        )]
    return []


def s007_image_slide_has_description(slide: SlideContent, idx: int) -> list[V1Finding]:
    if slide.layout != "image":
        return []
    if not slide.image_description or len(slide.image_description) < 10:
        return [V1Finding(
            rule="V1-S007", severity="warning",
            message=f"Slide {idx + 1}: image slide has no/vague image_description.",
            slide_index=idx,
        )]
    return []


def s008_chart_slide_has_data(slide: SlideContent, idx: int) -> list[V1Finding]:
    if slide.layout != "chart":
        return []
    if not slide.chart_data or len(slide.chart_data.strip()) < 5:
        return [V1Finding(
            rule="V1-S008", severity="error",
            message=f"Slide {idx + 1}: chart slide has no chart_data.",
            slide_index=idx,
        )]
    return []


def s009_two_column_has_content(slide: SlideContent, idx: int) -> list[V1Finding]:
    if slide.layout != "two_column":
        return []
    if not slide.left_column.strip() and not slide.right_column.strip():
        return [V1Finding(
            rule="V1-S009", severity="error",
            message=f"Slide {idx + 1}: two_column layout has no column content.",
            slide_index=idx,
        )]
    return []


def s010_visual_text_ratio(slide: SlideContent, idx: int) -> list[V1Finding]:
    """Slides with images should have reduced text."""
    if slide.layout != "image":
        return []
    base_limit = MAX_CHARS.get("image", 200)
    reduced_limit = int(base_limit * 0.7)  # 30% less text when image present
    total = _total_chars(slide)
    if total > reduced_limit:
        return [V1Finding(
            rule="V1-S010", severity="warning",
            message=(
                f"Slide {idx + 1}: {total} chars on image slide exceeds "
                f"reduced limit ({reduced_limit}). Reduce text for visual balance."
            ),
            slide_index=idx,
        )]
    return []


def s011_content_density(slide: SlideContent, idx: int) -> list[V1Finding]:
    """Content characters per cm² must not exceed threshold."""
    if slide.layout in ("title", "section"):
        return []
    total = _total_chars(slide)
    # 16:9 content area: (33.867 - 2*2.2) * (19.05 - 5.2 - 1.0) ≈ 29.467 * 12.85 ≈ 378.7 cm²
    area = 378.7
    density = total / area if area > 0 else 0
    max_density = 2.5
    if density > max_density:
        return [V1Finding(
            rule="V1-S011", severity="warning",
            message=(
                f"Slide {idx + 1}: content density {density:.1f} chars/cm² "
                f"exceeds maximum {max_density}. Slide will feel cramped."
            ),
            slide_index=idx,
        )]
    return []


def s012_headline_is_statement(slide: SlideContent, idx: int) -> list[V1Finding]:
    """Headline should be a statement, not just a topic label."""
    if slide.layout in ("title", "section"):
        return []
    headline = slide.title.strip()
    if not headline:
        return []
    words = headline.split()
    if len(words) <= 3 and len(headline) < 30:
        return [V1Finding(
            rule="V1-S012", severity="warning",
            message=f"Slide {idx + 1}: title '{headline}' appears to be a topic label, not a statement.",
            slide_index=idx,
        )]
    return []


# ── Main entry point ──────────────────────────────────────────────────────────

_ALL_CHECKS = [
    s001_headline_required,
    s002_headline_max_length,
    s003_bullet_max_count,
    s004_bullet_max_length,
    s005_no_generic_headline,
    s006_total_text_density,
    s007_image_slide_has_description,
    s008_chart_slide_has_data,
    s009_two_column_has_content,
    s010_visual_text_ratio,
    s011_content_density,
    s012_headline_is_statement,
]


def validate_v1_slide(slide: SlideContent, slide_index: int) -> list[V1Finding]:
    """Run all V1 slide-level checks and return combined findings."""
    findings: list[V1Finding] = []
    for check in _ALL_CHECKS:
        findings.extend(check(slide, slide_index))
    return findings


def validate_v1_presentation(data: PresentationData) -> list[V1Finding]:
    """Validate all slides in a V1 PresentationData."""
    all_findings: list[V1Finding] = []
    for i, slide in enumerate(data.slides):
        all_findings.extend(validate_v1_slide(slide, i))

    errors = [f for f in all_findings if f.severity == "error"]
    warnings = [f for f in all_findings if f.severity == "warning"]
    if errors or warnings:
        logger.warning(
            f"[V1 Validation] {len(errors)} errors, {len(warnings)} warnings "
            f"across {len(data.slides)} slides"
        )
        for f in all_findings:
            logger.info(f"  [{f.rule}] {f.message}")

    return all_findings
