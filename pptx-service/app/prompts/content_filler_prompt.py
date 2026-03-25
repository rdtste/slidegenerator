"""Content Filler prompt — finalizes text for ONE slide."""

from __future__ import annotations

import json


def build_content_filler_prompt(
    slide_plan: dict,
    audience_profile: str,
    image_style_profile: str,
) -> str:
    """Build the Content Filler prompt for a single slide.

    Args:
        slide_plan: Single SlidePlan dict to fill with final text.
        audience_profile: Audience profile text from profiles.py.
        image_style_profile: Image style profile text from profiles.py.

    Returns:
        Complete prompt string.
    """
    slide_json = json.dumps(slide_plan, ensure_ascii=False, indent=2)

    return f"""\
You are a Texter fuer Geschaeftspraesentationen.

TASK:
Finalize the text content for ONE slide. Replace placeholder text with
specific, concrete, audience-appropriate content. Preserve the JSON structure
exactly — only improve the text values.

SLIDE PLAN:
{slide_json}

AUDIENCE:
{audience_profile}

IMAGE STYLE:
{image_style_profile}

TEXT RULES (CRITICAL):
1. headline: max 70 characters. Must be a STATEMENT with substance, NOT a topic label.
   The headline must transport an insight, verdict, or conclusion.
   BAD: "Bier im Mittelalter" — GOOD: "Kloester bewahrten das Brauwissen und professionalisierten es."
   BAD: "Aktuelle Trends" — GOOD: "Craft Beer gewinnt durch Regionalitaet und alkoholfreie Innovation."
   If the headline sounds like a Wikipedia article title, rewrite it as an assertion.
2. subheadline: max 120 characters.
3. core_message: max 150 characters.
4. speaker_notes: max 600 characters. Write as spoken text for the presenter.

BULLET RULES:
- Each bullet text: max 80 characters.
- Each bold_prefix: max 25 characters.
- For management audience: EVERY bullet MUST have a non-empty bold_prefix.
- Be specific: use numbers, names, dates. Never write generic filler.
- No bullet may start with a dash or bullet character (plain text only).

CONTENT BLOCK LIMITS:
- kpi.label: max 35 chars, kpi.value: max 20 chars, kpi.delta: max 20 chars
- card.title: max 35 chars, card.body: max 120 chars
- quote.text: max 180 chars, quote.attribution: max 60 chars
- timeline_entry.date: max 25, .title: max 50, .description: max 100
- process_step.title: max 40, .description: max 100
- comparison_column.column_label: max 30
- label_value: label max 30, value max 50
- text.text: max 250 chars

QUALITY CHECKS:
- No lorem ipsum, no "[placeholder]", no "XYZ".
- Every number should be plausible in context.
- Language: German unless briefing specifies otherwise.
- Tone must match audience profile above.

COMPLETENESS CHECK (apply before outputting):
Before returning, verify:
- Is the headline a statement (not a topic label)?
- Are all content blocks fully populated (no empty fields, no placeholder text)?
- Does every bullet have real content (min 30 chars)?
- For image_text_split: is there a subheadline AND 2-3 supporting points?
- For three_cards: does each card have title (min 10 chars) AND body (min 40 chars)?
- For timeline: does each entry have date AND title AND description (min 30 chars)?
- Would this slide look professional and complete when rendered, or does it look half-empty?
If any check fails, fix the content before outputting.

OUTPUT:
Return the SAME JSON structure as the input, with all text fields finalized.
Add a "text_metrics" object:
{{
  "total_chars": "int — sum of all visible text characters",
  "bullet_count": "int — number of bullet items",
  "max_bullet_length": "int — length of longest bullet text",
  "headline_length": "int — length of headline"
}}

Output ONLY valid JSON. No markdown fences, no explanation text."""
