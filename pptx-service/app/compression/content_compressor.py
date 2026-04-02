"""Content Compressor — semantic reduction before rendering.

This is NOT truncation. The compressor:
1. Extracts the core assertion from each slide
2. Removes filler words and redundant clauses
3. Enforces one dominant element per slide
4. Respects hard word/char budgets from LayoutFamily
5. Splits overfull slides when compression alone isn't enough

Sits between Stage 3 (Slide Plan) and Stage 5 (Content Fill) in the V2 pipeline.
In the V3 target architecture, this becomes a mandatory pre-render gate.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from app.domain.models import (
    CompressedSlideSpec,
    LayoutBudget,
    LayoutFamily,
    LAYOUT_BUDGETS,
    VisualRole,
)
from app.schemas.models import (
    BulletsBlock,
    CardBlock,
    ComparisonColumnBlock,
    ContentBlock,
    KpiBlock,
    ProcessStepBlock,
    SlidePlan,
    SlideType,
    TextBlock,
    TimelineEntryBlock,
    QuoteBlock,
    PresentationPlan,
)

logger = logging.getLogger(__name__)

# ── SlideType → LayoutFamily mapping ─────────────────────────────────────────

_TYPE_TO_FAMILY: dict[SlideType, LayoutFamily] = {
    SlideType.TITLE_HERO: LayoutFamily.HERO,
    SlideType.SECTION_DIVIDER: LayoutFamily.SECTION_DIVIDER,
    SlideType.KEY_STATEMENT: LayoutFamily.KEY_FACT,
    SlideType.BULLETS_FOCUSED: LayoutFamily.CARD_GRID,
    SlideType.THREE_CARDS: LayoutFamily.CARD_GRID,
    SlideType.KPI_DASHBOARD: LayoutFamily.KEY_FACT,
    SlideType.IMAGE_TEXT_SPLIT: LayoutFamily.HERO,
    SlideType.COMPARISON: LayoutFamily.COMPARISON,
    SlideType.TIMELINE: LayoutFamily.TIMELINE,
    SlideType.PROCESS_FLOW: LayoutFamily.TIMELINE,
    SlideType.CHART_INSIGHT: LayoutFamily.KEY_FACT,
    SlideType.IMAGE_FULLBLEED: LayoutFamily.HERO,
    SlideType.AGENDA: LayoutFamily.CARD_GRID,
    SlideType.CLOSING: LayoutFamily.CLOSING,
}


def _resolve_family(slide_type: SlideType) -> LayoutFamily:
    return _TYPE_TO_FAMILY.get(slide_type, LayoutFamily.CARD_GRID)


# ── Text compression helpers ─────────────────────────────────────────────────

# Filler patterns (German + English)
_FILLER_PATTERNS = [
    r"\b(grundsaetzlich|im Grunde genommen|letztendlich|sozusagen)\b",
    r"\b(essentially|basically|actually|generally speaking|in terms of)\b",
    r"\b(es ist wichtig zu erwaehnen|es sei darauf hingewiesen)\b",
    r"\b(it is worth noting|it should be noted|as mentioned earlier)\b",
    r"\b(wie bereits erwaehnt|wie schon gesagt)\b",
]
_FILLER_RE = re.compile("|".join(_FILLER_PATTERNS), re.IGNORECASE)


def _remove_filler(text: str) -> str:
    """Remove filler words and phrases."""
    cleaned = _FILLER_RE.sub("", text)
    # Collapse multiple spaces
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
    # Remove orphaned commas
    cleaned = re.sub(r",\s*,", ",", cleaned)
    cleaned = re.sub(r"^\s*,\s*", "", cleaned)
    return cleaned


def _compress_to_word_budget(text: str, max_words: int) -> str:
    """Compress text to fit within a word budget.

    Strategy: keep the first sentence (core assertion) and trim from the end.
    This is the fallback when semantic compression isn't enough.
    """
    words = text.split()
    if len(words) <= max_words:
        return text

    # Try to keep complete sentences
    sentences = re.split(r"(?<=[.!?])\s+", text)
    result_words: list[str] = []
    for sentence in sentences:
        s_words = sentence.split()
        if len(result_words) + len(s_words) <= max_words:
            result_words.extend(s_words)
        else:
            break

    if not result_words:
        # Even first sentence exceeds budget — hard cut at word boundary
        result_words = words[:max_words]

    return " ".join(result_words)


def _compress_to_char_budget(text: str, max_chars: int) -> str:
    """Hard char limit with word-boundary cut."""
    if len(text) <= max_chars:
        return text
    truncated = text[: max_chars - 1]
    last_space = truncated.rfind(" ")
    if last_space > max_chars // 2:
        truncated = truncated[:last_space]
    return truncated.rstrip()


# ── Content block extraction ─────────────────────────────────────────────────

def _extract_text_from_blocks(blocks: list[ContentBlock]) -> str:
    """Extract all text content from content blocks for measurement."""
    parts: list[str] = []
    for block in blocks:
        if isinstance(block, BulletsBlock):
            for item in block.items:
                parts.append(f"{item.bold_prefix} {item.text}".strip())
        elif isinstance(block, KpiBlock):
            parts.append(f"{block.label}: {block.value} {block.delta}".strip())
        elif isinstance(block, TextBlock):
            parts.append(block.text)
        elif isinstance(block, CardBlock):
            parts.append(f"{block.title}: {block.body}".strip())
        elif isinstance(block, QuoteBlock):
            parts.append(f"{block.text} — {block.attribution}".strip())
        elif isinstance(block, ComparisonColumnBlock):
            parts.append(f"{block.column_label}: " + ", ".join(block.items))
        elif isinstance(block, TimelineEntryBlock):
            parts.append(f"{block.date} {block.title}: {block.description}".strip())
        elif isinstance(block, ProcessStepBlock):
            parts.append(f"{block.title}: {block.description}".strip())
    return "\n".join(parts)


def _extract_bullets(blocks: list[ContentBlock]) -> list[str]:
    """Extract bullet texts from content blocks."""
    for block in blocks:
        if isinstance(block, BulletsBlock):
            return [
                f"{item.bold_prefix} {item.text}".strip() if item.bold_prefix else item.text
                for item in block.items
            ]
    return []


def _extract_elements(blocks: list[ContentBlock]) -> list[dict]:
    """Extract structured elements (cards, KPIs, timeline entries, etc.)."""
    elements: list[dict] = []
    for block in blocks:
        if isinstance(block, CardBlock):
            elements.append({"type": "card", "title": block.title, "body": block.body})
        elif isinstance(block, KpiBlock):
            elements.append({
                "type": "kpi", "label": block.label,
                "value": block.value, "delta": block.delta,
            })
        elif isinstance(block, TimelineEntryBlock):
            elements.append({
                "type": "timeline", "date": block.date,
                "title": block.title, "description": block.description,
            })
        elif isinstance(block, ProcessStepBlock):
            elements.append({
                "type": "process_step", "step": block.step_number,
                "title": block.title, "description": block.description,
            })
        elif isinstance(block, ComparisonColumnBlock):
            elements.append({
                "type": "comparison", "label": block.column_label,
                "items": block.items,
            })
    return elements


# ── Core compression logic ───────────────────────────────────────────────────

def compress_slide(slide: SlidePlan) -> CompressedSlideSpec:
    """Compress a single SlidePlan into a budget-compliant CompressedSlideSpec.

    Steps:
    1. Map SlideType → LayoutFamily → LayoutBudget
    2. Extract core assertion (headline + core_message)
    3. Remove filler from all text
    4. Enforce element count limits
    5. Compress text to word/char budgets
    6. Record compression ratio
    """
    family = _resolve_family(slide.slide_type)
    budget = LAYOUT_BUDGETS[family]

    # Measure original size
    original_text = _extract_text_from_blocks(slide.content_blocks)
    original_chars = len(slide.headline) + len(slide.subheadline) + len(original_text)

    # Step 1: Core assertion — prefer core_message, fall back to headline
    core_assertion = slide.core_message.strip() or slide.headline.strip()

    # Step 2: Compress headline
    headline = _remove_filler(slide.headline)
    headline = _compress_to_word_budget(headline, budget.max_headline_words)
    headline = _compress_to_char_budget(headline, budget.max_headline_chars)

    # Step 3: Build supporting text from subheadline or first TextBlock
    supporting = ""
    if slide.subheadline:
        supporting = _remove_filler(slide.subheadline)
    else:
        for block in slide.content_blocks:
            if isinstance(block, TextBlock) and block.text.strip():
                supporting = _remove_filler(block.text)
                break

    if budget.max_body_words > 0 and supporting:
        supporting = _compress_to_word_budget(supporting, budget.max_body_words)
        supporting = _compress_to_char_budget(supporting, budget.max_body_chars)
    elif budget.max_body_words == 0:
        supporting = ""

    # Step 4: Extract and limit bullets
    bullets = _extract_bullets(slide.content_blocks)
    bullets = [_remove_filler(b) for b in bullets]
    if budget.max_bullets > 0:
        bullets = bullets[:budget.max_bullets]
        bullets = [
            _compress_to_word_budget(b, budget.max_bullet_words)
            for b in bullets
        ]
    else:
        bullets = []

    # Step 5: Extract and limit structured elements
    elements = _extract_elements(slide.content_blocks)
    elements = elements[:budget.max_elements]

    # Compress text within elements
    for elem in elements:
        for key in ("title", "label", "description", "body"):
            if key in elem and isinstance(elem[key], str):
                elem[key] = _remove_filler(elem[key])
                elem[key] = _compress_to_char_budget(elem[key], 80)
        if "items" in elem and isinstance(elem["items"], list):
            elem["items"] = [
                _compress_to_char_budget(_remove_filler(str(item)), 60)
                for item in elem["items"][:budget.max_elements]
            ]

    # Step 6: Determine visual role
    visual_role = VisualRole.NONE
    if slide.visual:
        from app.schemas.models import VisualType, ImageRole
        if slide.visual.chart_spec:
            visual_role = VisualRole.DATA_CHART
        elif slide.visual.image_role == ImageRole.HERO:
            visual_role = VisualRole.HERO_IMAGE
        elif slide.visual.image_role in (ImageRole.SUPPORTING, ImageRole.DECORATIVE):
            visual_role = VisualRole.SUPPORTING_ICON
        elif slide.visual.type == VisualType.DIAGRAM:
            visual_role = VisualRole.DIAGRAM

    visual_desc = ""
    if slide.visual and slide.visual.image_description:
        visual_desc = _compress_to_char_budget(slide.visual.image_description, 120)

    # Measure compressed size
    compressed_chars = len(headline) + len(supporting) + sum(len(b) for b in bullets)
    compressed_chars += sum(len(str(e)) for e in elements)

    spec = CompressedSlideSpec(
        position=slide.position,
        layout_family=family,
        core_assertion=_compress_to_char_budget(core_assertion, 120),
        headline=headline,
        supporting_text=supporting,
        bullets=bullets,
        elements=elements,
        visual_role=visual_role,
        visual_description=visual_desc,
        speaker_notes=_compress_to_char_budget(slide.speaker_notes, 200),
        original_char_count=original_chars,
        compressed_char_count=compressed_chars,
        compression_ratio=original_chars / max(compressed_chars, 1),
    )

    # Log compression results
    violations = spec.exceeds_budget()
    if violations:
        logger.warning(
            f"[Compressor] Slide {slide.position} ({family.value}): "
            f"still exceeds budget after compression: {violations}"
        )
    else:
        logger.info(
            f"[Compressor] Slide {slide.position} ({family.value}): "
            f"{original_chars} → {compressed_chars} chars "
            f"(ratio {spec.compression_ratio:.1f}x)"
        )

    return spec


def compress_presentation(plan: PresentationPlan) -> list[CompressedSlideSpec]:
    """Compress all slides in a presentation plan.

    Returns a list of CompressedSlideSpecs ready for the quality gate.
    Slides that still exceed budget after compression are flagged — the
    quality gate will decide whether to block and replan.
    """
    compressed: list[CompressedSlideSpec] = []
    total_original = 0
    total_compressed = 0

    for slide in plan.slides:
        spec = compress_slide(slide)
        compressed.append(spec)
        total_original += spec.original_char_count
        total_compressed += spec.compressed_char_count

    logger.info(
        f"[Compressor] Presentation: {total_original} → {total_compressed} chars "
        f"(overall ratio {total_original / max(total_compressed, 1):.1f}x), "
        f"{len(compressed)} slides"
    )

    # Report slides that still violate budgets
    violating = [s for s in compressed if s.exceeds_budget()]
    if violating:
        logger.warning(
            f"[Compressor] {len(violating)}/{len(compressed)} slides "
            f"still exceed budget after compression — quality gate will evaluate"
        )

    return compressed


def needs_split(spec: CompressedSlideSpec) -> bool:
    """Check if a compressed slide should be split into multiple slides.

    A slide needs splitting when:
    - Total chars exceed 2x the budget (compression can't save it)
    - Element count exceeds 2x the max (too many cards/KPIs/steps)
    """
    budget = spec.budget
    total = spec.compressed_char_count
    if total > budget.max_total_chars * 2:
        return True
    if len(spec.elements) > budget.max_elements * 2:
        return True
    return False


def split_slide(spec: CompressedSlideSpec) -> list[CompressedSlideSpec]:
    """Split an overfull compressed slide into multiple slides.

    Strategy:
    - Keep headline on first slide
    - Distribute elements evenly across slides
    - Each resulting slide gets re-compressed
    """
    if not needs_split(spec):
        return [spec]

    budget = spec.budget
    max_per_slide = budget.max_elements

    if spec.elements and len(spec.elements) > max_per_slide:
        # Split by elements
        chunks = [
            spec.elements[i:i + max_per_slide]
            for i in range(0, len(spec.elements), max_per_slide)
        ]
    elif spec.bullets and len(spec.bullets) > budget.max_bullets:
        # Split by bullets
        max_b = max(budget.max_bullets, 1)
        bullet_chunks = [
            spec.bullets[i:i + max_b]
            for i in range(0, len(spec.bullets), max_b)
        ]
        chunks = [[{"type": "bullets", "items": bc}] for bc in bullet_chunks]
    else:
        return [spec]

    result: list[CompressedSlideSpec] = []
    for i, chunk in enumerate(chunks):
        new_spec = CompressedSlideSpec(
            position=spec.position + i,
            layout_family=spec.layout_family,
            core_assertion=spec.core_assertion if i == 0 else "",
            headline=spec.headline if i == 0 else f"{spec.headline} ({i + 1})",
            supporting_text=spec.supporting_text if i == 0 else "",
            bullets=chunk[0].get("items", []) if chunk and isinstance(chunk[0], dict) and chunk[0].get("type") == "bullets" else [],
            elements=chunk if chunk and not (isinstance(chunk[0], dict) and chunk[0].get("type") == "bullets") else [],
            visual_role=spec.visual_role if i == 0 else VisualRole.NONE,
            visual_description=spec.visual_description if i == 0 else "",
            speaker_notes=spec.speaker_notes if i == 0 else "",
            original_char_count=spec.original_char_count // len(chunks),
            compressed_char_count=0,  # Will be recalculated
        )
        # Recalculate compressed chars
        cc = len(new_spec.headline) + len(new_spec.supporting_text)
        cc += sum(len(b) for b in new_spec.bullets)
        cc += sum(len(str(e)) for e in new_spec.elements)
        new_spec.compressed_char_count = cc
        new_spec.compression_ratio = new_spec.original_char_count / max(cc, 1)
        result.append(new_spec)

    logger.info(
        f"[Compressor] Slide {spec.position} split into {len(result)} slides"
    )
    return result
