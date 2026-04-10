"""Storyline Planner prompt — creates narrative arc with story beats."""

from __future__ import annotations

import json


def build_storyline_prompt(briefing: dict) -> str:
    """Build the Storyline Planner prompt.

    Args:
        briefing: InterpretedBriefing dict (output of Stage 1).

    Returns:
        Complete prompt string.
    """
    briefing_json = json.dumps(briefing, ensure_ascii=False, indent=2)

    return f"""\
You are a Storytelling-Experte for business presentations.

TASK:
Create a narrative arc (Storyline) for a presentation based on the briefing below.
Each story beat represents ONE key moment in the presentation's narrative.

BRIEFING:
{briefing_json}

NARRATIVE ARC SELECTION:
- "situation_complication_resolution": Best for problem-solving, strategy decks.
- "problem_solution": Direct approach for pitches and proposals.
- "chronological": Timeline-based for historical topics, development arcs, biographical subjects, project updates. REQUIRED when topic involves progression over time.
- "thematic_cluster": Topic-by-topic for broad overviews, training.
- "compare_decide": Side-by-side evaluation for decision decks.

RULES:
1. Each beat has exactly ONE core_message (max 150 characters).
2. First beat MUST be beat_type "opening".
3. Last beat MUST be beat_type "closing".
4. Maximum 2 beats may have beat_type "transition".
5. total_beats must equal the number of beats in the array.
6. Number of beats should roughly match requested_slide_count from briefing
   (some beats may produce multiple slides, so beats <= requested_slide_count).
7. suggested_slide_types: list 1-3 suitable SlideType values per beat.
   Allowed types: title_hero, section_divider, key_statement, bullets_focused,
   three_cards, kpi_dashboard, image_text_split, comparison, timeline,
   process_flow, chart_insight, image_fullbleed, agenda, closing.
8. emotional_intent per beat: confidence, urgency, curiosity, resolution, inspiration.
9. Set evidence_needed=true for beats that need data, charts, or proof points.

CHRONOLOGICAL/HISTORICAL TOPICS:
If the briefing's content_themes include "chronological", "historical", "timeline",
or "development", or if the topic inherently involves progression over time:
1. Use narrative_arc "chronological".
2. Structure beats as a visible progression through time periods or phases.
3. At least one beat must be beat_type "evidence" with suggested_slide_types ["timeline"].
4. The second-to-last beat should address current relevance or modern transformation.
5. The closing beat must synthesize: what endured, what changed, what matters now.
6. Each beat's core_message must be a STATEMENT, not a topic label.
   BAD: "Die Antike" — GOOD: "Schon die Sumerer brauten Bier als Grundnahrungsmittel."
7. Avoid beats that merely name an era without an insight about it.

FACT SAFETY:
- Only plan beats around facts and themes actually present in the briefing.
- Never plan a KPI/evidence beat unless the briefing provides concrete data.
- If the briefing is thin on facts, plan fewer evidence beats and more
  insight/context beats with qualitative statements.
- Set evidence_needed=false for beats where the briefing provides no data.
- It is better to plan a simpler, honest deck than an ambitious deck that
  will require inventing numbers to fill.

BEAT QUALITY:
Every beat's core_message must be a concrete assertion or insight, never just a topic name.
BAD core_messages: "Mittelalter", "Industrialisierung", "Moderne Trends"
GOOD core_messages: "Kloester retteten das Brauwissen und machten es zur Wissenschaft.",
  "Die Dampfmaschine ermoeglichte erstmals industrielle Bierproduktion.",
  "Craft Beer setzt auf Vielfalt statt Massenproduktion."

OUTPUT SCHEMA (Storyline):
{{
  "narrative_arc": "enum — one of the arc types above",
  "total_beats": "integer",
  "beats": [
    {{
      "position": "integer >= 1, sequential",
      "beat_type": "enum: opening | context | evidence | insight | action | transition | closing",
      "core_message": "string, max 150 chars — the ONE takeaway for this beat",
      "content_theme": "string — which content_theme from briefing this covers",
      "emotional_intent": "enum: confidence | urgency | curiosity | resolution | inspiration",
      "evidence_needed": "boolean",
      "suggested_slide_types": ["SlideType enum values"]
    }}
  ]
}}

Output ONLY valid JSON matching the schema above. No markdown fences, no explanation text."""
