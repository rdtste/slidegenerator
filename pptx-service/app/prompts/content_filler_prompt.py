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
1. headline: max 70 characters, ideally under 55. Must be a STATEMENT with substance, NOT a topic label.
   The headline must transport an insight, verdict, or conclusion.
   BAD: "Bier im Mittelalter" — GOOD: "Kloester professionalisierten das Brauwissen."
   BAD: "Aktuelle Trends" — GOOD: "Craft Beer waechst durch Regionalitaet."
   If the headline sounds like a Wikipedia article title, rewrite it as a short assertion.
   SHORTEN actively: cut filler words ("Art und Weise", "im Bereich von"), use strong verbs.
2. subheadline: max 90 characters. Must be SHORTER than the shortest body text element.
   If the subheadline is longer than a bullet or card body, shorten the subheadline.
3. core_message: max 120 characters. One sentence. No compound sentences.
4. speaker_notes: max 500 characters. Write as spoken text for the presenter.

READABILITY RULES (MANDATORY):
- Every text block must be a SCANNABLE VISUAL UNIT, not a paragraph.
- Max 25 words per bullet item. If longer, split or compress.
- Max 15 words per card body sentence. Cards are not paragraphs.
- No text block may exceed 3 visible lines when rendered.
- Labels and values must be separate: "Umsatz" as label, "+12%" as value — never "Umsatz: +12%" in one string.
- Prefer numbers, facts, names over generic descriptions.
- Each slide must be graspable in under 8 seconds of reading.

BULLET RULES:
- Each bullet text: max 60 characters.
- Each bold_prefix: max 20 characters.
- Max 3 bullets per slide. If more content, use cards or process_flow instead.
- For management audience: EVERY bullet MUST have a non-empty bold_prefix.
- Be specific: use numbers, names, dates. Never write generic filler.
- No bullet may start with a dash or bullet character (plain text only).

CONTENT BLOCK LIMITS:
- kpi.label: max 30 chars, kpi.value: max 15 chars, kpi.delta: max 15 chars
- card.title: max 30 chars, card.body: max 80 chars (1 sentence only, no paragraphs)
- quote.text: max 150 chars, quote.attribution: max 50 chars
- timeline_entry.date: max 20, .title: max 40, .description: max 80
- process_step.title: max 35, .description: max 80
- comparison_column.column_label: max 25, max 4 items each max 50 chars
- label_value: label max 25, value max 40
- text.text: max 200 chars

QUALITY CHECKS:
- No lorem ipsum, no "[placeholder]", no "XYZ".
- Every number should be plausible in context.
- Language: German unless briefing specifies otherwise.
- Tone must match audience profile above.
- WORD COUNT CHECK: count words in each text element. If any exceeds its limit, shorten.

COMPLETENESS CHECK (apply before outputting):
Before returning, verify:
- Is the headline a short statement (not a topic label)? Under 60 chars ideally?
- Is the subheadline shorter than the body content?
- Are all content blocks fully populated (no empty fields, no placeholder text)?
- Does every bullet have real content (min 20 chars, max 60 chars)?
- For three_cards: does each card have title (max 30 chars) AND body (max 80 chars, 1 sentence)?
- For timeline: does each entry have date AND title AND description (max 80 chars)?
- Would this slide be graspable in 8 seconds, or is it a text wall?
- Does any element have more than 3 lines of text? If yes, shorten.
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
