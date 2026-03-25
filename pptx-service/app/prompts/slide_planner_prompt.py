"""Slide Planner prompt — translates story beats into concrete SlidePlans."""

from __future__ import annotations

import json


def build_slide_planner_prompt(
    storyline: dict,
    briefing: dict,
    slide_type_catalog: str,
    transform_rules: str,
    audience_profile: str,
    image_style_profile: str,
) -> str:
    """Build the Slide Planner prompt.

    Args:
        storyline: Storyline dict (output of Stage 2).
        briefing: InterpretedBriefing dict (output of Stage 1).
        slide_type_catalog: Formatted string listing all allowed slide types
            with their constraints (max bullets, required fields, etc.).
        transform_rules: Text describing beat-to-slide transformation rules.
        audience_profile: Audience profile text from profiles.py.
        image_style_profile: Image style profile text from profiles.py.

    Returns:
        Complete prompt string.
    """
    storyline_json = json.dumps(storyline, ensure_ascii=False, indent=2)
    briefing_json = json.dumps(briefing, ensure_ascii=False, indent=2)

    return f"""\
You are a Praesentations-Architekt (Slide Planner).

TASK:
Translate each story beat into one or more SlidePlans. Choose the optimal
slide_type for each beat and define headline, content_blocks, and visual spec.

BRIEFING:
{briefing_json}

STORYLINE:
{storyline_json}

AUDIENCE:
{audience_profile}

IMAGE STYLE:
{image_style_profile}

ALLOWED SLIDE TYPES — ONLY these types are permitted:
{slide_type_catalog}

BEAT-TO-SLIDE RULES:
{transform_rules}

SEQUENCE RULES (CRITICAL):
1. First slide MUST be slide_type "title_hero".
2. Last slide MUST be slide_type "closing".
3. No two consecutive slides may be "bullets_focused".
4. "section_divider" must appear before a new thematic section.
5. "kpi_dashboard" must have exactly 3 or 4 KPI content_blocks.
6. "three_cards" must have exactly 3 card content_blocks.
7. "comparison" must have exactly 2 comparison_column content_blocks.
8. "timeline" must have 3-6 timeline_entry content_blocks.
9. "process_flow" must have 3-5 process_step content_blocks.
10. "chart_insight" must include visual.chart_spec with valid chart data.
11. Position values must be sequential starting at 1.
12. beat_ref must reference a valid beat position from the storyline.

CONTENT BLOCK RULES:
- bullets: items array, each item has text (max 80 chars) and bold_prefix (max 25 chars)
- kpi: label (max 35), value (max 20), trend (up|down|neutral), delta (max 20)
- card: title (max 35), body (max 120), icon_hint
- quote: text (max 180), attribution (max 60)
- timeline_entry: date (max 25), title (max 50), description (max 100)
- process_step: step_number, title (max 40), description (max 100)
- comparison_column: column_label (max 30), items array
- label_value: pairs array with label (max 30) and value (max 50)
- text: text field (max 250)

TITLE LOGIC (CRITICAL — every title must follow these rules):
Headlines must be STATEMENTS, never topic labels or chapter headings.
A good title transports an insight, verdict, or conclusion.
A title that sounds like a school essay heading is INVALID.

INVALID titles (topic labels):
- "Industrialisierung & Moderne"
- "Bier im Mittelalter"
- "Aktuelle Entwicklungen"
- "Die Wissenschaft des Bieres"

VALID titles (statements with substance):
- "Die Industrialisierung machte Bier erstmals global skalierbar."
- "Kloester bewahrten das Brauwissen und professionalisierten es."
- "Craft Beer gewinnt durch Differenzierung und Regionalitaet."
- "Das Reinheitsgebot definiert Bierqualitaet seit 1516."

Rule: If a title could be a Wikipedia article heading, it is too generic.

SLIDE TYPE COMPLETENESS (CRITICAL — no half-filled templates):
A slide type is only valid when fully populated. Underfilled slides are INVALID.

Minimum requirements per type:
- title_hero: headline + subheadline. Only for opening slide or max 1 transition.
- section_divider: headline + core_message. Max 2 per deck.
- key_statement: headline + 1 quote or text block. Max 2 per deck.
- image_text_split: headline + subheadline + image + 2-3 bullets or text block. Image MUST have functional purpose.
- three_cards: headline + exactly 3 cards, each with title + body (min 40 chars each).
- kpi_dashboard: headline + 3-4 KPIs, each with label + value + trend.
- timeline: headline + min 4 timeline entries, each with date + title + description.
- comparison: headline + exactly 2 columns with min 3 items each.
- process_flow: headline + 3-5 steps, each with title + description.
- bullets_focused: headline + 1 bullets block with 2-3 substantive items.
- closing: headline + 3 summary bullets or quote. Must feel like a conclusion, not filler.

A slide that looks like "title + image only" or "title + divider line" is INVALID.

HISTORICAL AND CHRONOLOGICAL THEMES:
When the topic is historical, biographical, or involves development over time:
1. Use narrative_arc "chronological" if not already set.
2. Include AT LEAST 1 timeline slide showing the full arc.
3. Include AT LEAST 1 comparison or image_text_split showing before/after or epoch contrast.
4. Structure the deck chronologically with visible phase transitions.
5. Use section_dividers to mark major era transitions.
6. The penultimate slide should show current relevance or "what changed".
7. The closing slide must synthesize: what remains, what changed, what matters today.
FORBIDDEN: Listing epochs as near-identical text slides without visual differentiation.

IMAGE FUNCTION (every image must earn its place):
Every image must fulfill at least one of these roles:
- Transport zeitgeist or atmosphere of an era/context
- Visually anchor a historical phase or location
- Create contrast between epochs or states
- Emotionally or factually reinforce the core message
- Carry the layout composition as a hero element

If an image is interchangeable and adds no content value, it is too weak.
Set image_role to "supporting" or "evidence", never "decorative" (except image_fullbleed).
Write image_description as a specific, concrete scene — not a generic stock photo description.
BAD: "A modern brewery" — GOOD: "Industrial copper brewing kettles in a 19th century German brewery hall, steam rising, workers in leather aprons"

DECK DRAMATURGY (build a coherent story, not a slide collection):
For historical/chronological short decks (8-12 slides), prefer:
- Slide 1: Hero title
- Slide 2: Overview / Timeline showing the full arc
- Slides 3-N-2: Central development steps or epochs (varied types!)
- Slide N-1: Current relevance / transformation / significance today
- Slide N: Synthesis / closing statement

General rules:
- Max 2 hero/section/key_statement slides (low-content slides) in a row.
- Max 3 total low-content slides (title_hero + section_divider + key_statement) per deck.
- Every slide must have a clear information function — no filler slides.
- The deck must feel like a connected narrative, not a template showcase.

OUTPUT SCHEMA (PresentationPlan):
{{
  "audience": "enum",
  "image_style": "enum",
  "slides": [
    {{
      "position": "int >= 1",
      "slide_type": "SlideType enum",
      "beat_ref": "int — references storyline beat position",
      "headline": "string, max 70 chars",
      "subheadline": "string, max 120 chars",
      "core_message": "string, max 150 chars",
      "content_blocks": ["ContentBlock objects per type rules above"],
      "visual": {{
        "type": "enum: photo | illustration | icon | chart | diagram | none",
        "image_role": "enum: hero | supporting | decorative | evidence | none",
        "image_description": "string, max 250 chars — prompt for image generation",
        "chart_spec": "ChartSpec object or null"
      }},
      "speaker_notes": "string, max 600 chars",
      "transition_hint": "string"
    }}
  ],
  "metadata": {{
    "total_slides": "int",
    "estimated_duration_minutes": "int",
    "content_density": "enum: light | medium | dense"
  }}
}}

Output ONLY valid JSON matching the schema above. No markdown fences, no explanation text."""
