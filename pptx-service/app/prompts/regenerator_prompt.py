"""Slide Regenerator prompt — fixes ONE slide that failed validation."""

from __future__ import annotations

import json


def build_regenerator_prompt(
    failed_slide: dict,
    errors: list[str],
    context_before: dict | None,
    context_after: dict | None,
) -> str:
    """Build the Slide Regenerator prompt.

    Args:
        failed_slide: The slide dict that failed validation.
        errors: List of error/warning messages from the reviewer.
        context_before: Previous slide dict (for narrative continuity), or None.
        context_after: Next slide dict (for narrative continuity), or None.

    Returns:
        Complete prompt string.
    """
    failed_json = json.dumps(failed_slide, ensure_ascii=False, indent=2)
    errors_formatted = "\n".join(f"  - {e}" for e in errors)

    context_parts = []
    if context_before:
        context_parts.append(
            f"PREVIOUS SLIDE (for context):\n"
            f"{json.dumps(context_before, ensure_ascii=False, indent=2)}"
        )
    if context_after:
        context_parts.append(
            f"NEXT SLIDE (for context):\n"
            f"{json.dumps(context_after, ensure_ascii=False, indent=2)}"
        )
    context_section = "\n\n".join(context_parts) if context_parts else "No adjacent slides provided."

    return f"""\
You are a Praesentations-Architekt tasked with fixing a broken slide.

TASK:
Fix ONE slide that failed quality validation. You must address ALL reported
errors. You may change the slide_type if the current type cannot satisfy
the constraints.

FAILED SLIDE:
{failed_json}

REPORTED ERRORS:
{errors_formatted}

CONTEXT:
{context_section}

RULES:
1. Fix ALL reported errors. Every single one.
2. Preserve the position value — do not change it.
3. Preserve beat_ref — the narrative connection must stay.
4. You MAY change slide_type if the current type is fundamentally wrong
   (e.g., kpi_dashboard with only 1 KPI → switch to key_statement).
   When changing type, FULLY populate the new type — no half-filled slides.
5. Respect ALL character limits:
   - headline: max 70, subheadline: max 120, core_message: max 150
   - bullet text: max 80, bold_prefix: max 25
   - kpi.label: max 35, kpi.value: max 20, kpi.delta: max 20
   - card.title: max 35, card.body: max 120
   - quote.text: max 180, quote.attribution: max 60
   - timeline_entry.date: max 25, .title: max 50, .description: max 100
   - process_step.title: max 40, .description: max 100
   - comparison_column.column_label: max 30
   - speaker_notes: max 600
6. Structural constraints per type:
   - kpi_dashboard: exactly 3-4 kpi blocks
   - three_cards: exactly 3 card blocks, each with title + body (min 40 chars)
   - comparison: exactly 2 comparison_column blocks with min 3 items each
   - timeline: 3-6 timeline_entry blocks, each with date + title + description (min 30 chars)
   - process_flow: 3-5 process_step blocks, each with title + description
   - bullets_focused: 1 bullets block with 2-3 substantive items
   - image_text_split: headline + subheadline + image + 2-3 bullets/text
   - closing: headline + 3 summary bullets or quote, must feel like a conclusion
7. Ensure narrative continuity with adjacent slides.

TITLE LOGIC (CRITICAL):
Headlines must be STATEMENTS with substance, NEVER topic labels.
A statement transports an insight, verdict, or conclusion.
- BAD: "Industrialisierung & Moderne" → GOOD: "Die Industrialisierung machte Bier erstmals global skalierbar."
- BAD: "Aktuelle Trends" → GOOD: "Craft Beer gewinnt durch Regionalitaet und alkoholfreie Innovation."
If the headline could be a Wikipedia article heading, rewrite it as an assertion.

COMPLETENESS (CRITICAL):
The fixed slide must look professional and complete when rendered.
- No empty content blocks, no placeholder text.
- Every bullet must have real content (min 30 chars).
- Cards must have title (min 10 chars) AND body (min 40 chars).
- Timeline entries must have date AND title AND description (min 30 chars).
- If the current slide type cannot be fully populated, switch to a richer type.

IMAGE FUNCTION:
If the slide has an image, it must serve a purpose:
- image_role must be "supporting" or "evidence" or "hero", NOT "decorative"
- image_description must be specific and concrete (min 20 chars), not a generic stock photo prompt

OUTPUT:
Return the corrected slide as a single SlidePlan JSON object with the same
structure as the input. Include text_metrics if this is a FilledSlide.

Output ONLY valid JSON. No markdown fences, no explanation text."""
