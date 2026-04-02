"""Content leak detection rules (L001-L003).

Catches raw descriptors, placeholders, and metadata text that should never
appear as visible content on slides. These are the #1 source of
"unfinished-looking" slides.
"""

from __future__ import annotations

import re

from app.schemas.models import (
    BulletsBlock, CardBlock, ComparisonColumnBlock, ProcessStepBlock,
    QualityFinding, SlidePlan, TextBlock, TimelineEntryBlock, QuoteBlock,
)

# ── Patterns that indicate leaked internal metadata ───────────────────────────

# Icon/asset descriptors that should never be visible text
_DESCRIPTOR_PATTERNS: list[re.Pattern] = [
    # English icon descriptors
    re.compile(r'\b\w+\s+icon\b', re.IGNORECASE),
    re.compile(r'\bicon\s+of\b', re.IGNORECASE),
    re.compile(r'\bicon:\s', re.IGNORECASE),
    # German icon/image descriptors
    re.compile(r'\b(Symbol|Piktogramm|Grafik)\s+(von|fuer|eines|einer)\b', re.IGNORECASE),
    # Stock photo descriptions
    re.compile(r'\b(stock\s+photo|stock\s+image|stock\s+bild)\b', re.IGNORECASE),
    # Prompt-like descriptions (AI image generation prompts leaked)
    re.compile(r'\b(photorealistic|hyperrealistic|4k|8k|high.?resolution)\b', re.IGNORECASE),
    re.compile(r'\b(illustration\s+of|photo\s+of|image\s+of|picture\s+of)\b', re.IGNORECASE),
    re.compile(r'\b(Bild\s+von|Foto\s+von|Darstellung\s+von)\b', re.IGNORECASE),
    # Placeholder markers
    re.compile(r'\[.*?\]'),  # [placeholder], [Image: ...], [TODO]
    re.compile(r'\{.*?\}'),  # {template_var}
    re.compile(r'lorem\s+ipsum', re.IGNORECASE),
    re.compile(r'\bXYZ\b'),
    re.compile(r'\bTBD\b'),
    re.compile(r'\bTODO\b', re.IGNORECASE),
    re.compile(r'\bPLACEHOLDER\b', re.IGNORECASE),
]

# Specific icon hint values that commonly leak
_LEAKED_ICON_HINTS: set[str] = {
    "monastery icon", "shield icon", "scroll icon", "book icon",
    "gear icon", "people icon", "chart icon", "globe icon",
    "shield or scroll icon", "buch mit feder", "landkarte mit pin",
    "hopfenpflanze", "zahnrad", "menschen", "diagramm",
}


def _check_text_for_leaks(text: str) -> str | None:
    """Check a single text string for descriptor leaks. Returns description of leak or None."""
    if not text or len(text) < 3:
        return None

    text_lower = text.lower().strip()

    # Check against known leaked icon hints
    if text_lower in _LEAKED_ICON_HINTS:
        return f"raw icon descriptor '{text}'"

    # Check against descriptor patterns
    for pattern in _DESCRIPTOR_PATTERNS:
        match = pattern.search(text)
        if match:
            return f"descriptor pattern '{match.group()}' in '{text[:60]}'"

    return None


def _all_visible_texts(slide: SlidePlan) -> list[tuple[str, str]]:
    """Extract all visible text fields from a slide with their source label."""
    texts: list[tuple[str, str]] = []
    texts.append(("headline", slide.headline))
    texts.append(("subheadline", slide.subheadline))

    for i, block in enumerate(slide.content_blocks):
        if isinstance(block, BulletsBlock):
            for j, item in enumerate(block.items):
                texts.append((f"bullet[{j}].text", item.text))
                texts.append((f"bullet[{j}].bold_prefix", item.bold_prefix))
        elif isinstance(block, CardBlock):
            texts.append((f"card[{i}].title", block.title))
            texts.append((f"card[{i}].body", block.body))
            texts.append((f"card[{i}].icon_hint", block.icon_hint))
        elif isinstance(block, TextBlock):
            texts.append((f"text[{i}]", block.text))
        elif isinstance(block, QuoteBlock):
            texts.append((f"quote[{i}]", block.text))
        elif isinstance(block, ComparisonColumnBlock):
            texts.append((f"col[{i}].label", block.column_label))
            for j, item in enumerate(block.items):
                texts.append((f"col[{i}].item[{j}]", item))
        elif isinstance(block, TimelineEntryBlock):
            texts.append((f"timeline[{i}].title", block.title))
            texts.append((f"timeline[{i}].description", block.description))
        elif isinstance(block, ProcessStepBlock):
            texts.append((f"step[{i}].title", block.title))
            texts.append((f"step[{i}].description", block.description))

    return texts


# ── Rules ─────────────────────────────────────────────────────────────────────

def l001_no_descriptor_leaks(slide: SlidePlan, idx: int) -> list[QualityFinding]:
    """No raw descriptors, icon hints, or AI prompts in visible slide text."""
    findings: list[QualityFinding] = []

    for field_name, text in _all_visible_texts(slide):
        # Skip icon_hint fields — they're handled by the icon resolver
        if "icon_hint" in field_name:
            continue

        leak = _check_text_for_leaks(text)
        if leak:
            findings.append(QualityFinding(
                rule="L001", severity="error",
                message=f"Slide {idx + 1}: {field_name} contains {leak}.",
                slide_index=idx,
            ))

    return findings


def l002_no_empty_visible_fields(slide: SlidePlan, idx: int) -> list[QualityFinding]:
    """Content blocks that exist must have substantive content, not empty strings."""
    findings: list[QualityFinding] = []

    for i, block in enumerate(slide.content_blocks):
        if isinstance(block, CardBlock):
            if not block.title.strip():
                findings.append(QualityFinding(
                    rule="L002", severity="error",
                    message=f"Slide {idx + 1}: card[{i}] has empty title.",
                    slide_index=idx,
                ))
        elif isinstance(block, ProcessStepBlock):
            if not block.title.strip():
                findings.append(QualityFinding(
                    rule="L002", severity="error",
                    message=f"Slide {idx + 1}: step[{i}] has empty title.",
                    slide_index=idx,
                ))
        elif isinstance(block, TimelineEntryBlock):
            if not block.title.strip():
                findings.append(QualityFinding(
                    rule="L002", severity="error",
                    message=f"Slide {idx + 1}: timeline[{i}] has empty title.",
                    slide_index=idx,
                ))

    return findings


def l003_image_description_not_in_content(slide: SlidePlan, idx: int) -> list[QualityFinding]:
    """Image description must not appear in any visible text field.

    The image_description is an internal prompt for the image generator,
    not content that should be shown to the audience.
    """
    if not slide.visual or not slide.visual.image_description:
        return []

    img_desc = slide.visual.image_description.lower().strip()
    if len(img_desc) < 10:
        return []

    for field_name, text in _all_visible_texts(slide):
        if "icon_hint" in field_name:
            continue
        if text and img_desc in text.lower():
            return [QualityFinding(
                rule="L003", severity="error",
                message=(
                    f"Slide {idx + 1}: {field_name} contains the image_description text. "
                    f"Image descriptions are internal metadata, not slide content."
                ),
                slide_index=idx,
            )]

    return []


# ── Entry point ───────────────────────────────────────────────────────────────

_ALL_LEAK_CHECKS = [
    l001_no_descriptor_leaks,
    l002_no_empty_visible_fields,
    l003_image_description_not_in_content,
]


def validate_content_leaks(slide: SlidePlan, slide_index: int) -> list[QualityFinding]:
    """Run all content leak detection rules."""
    findings: list[QualityFinding] = []
    for check in _ALL_LEAK_CHECKS:
        findings.extend(check(slide, slide_index))
    return findings
