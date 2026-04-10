"""Quality Reviewer prompt — checks narrative coherence and quality."""

from __future__ import annotations

import json


def build_reviewer_prompt(slides: list[dict], briefing: dict) -> str:
    """Build the Quality Reviewer prompt.

    Args:
        slides: List of FilledSlide dicts (output of Stage 5).
        briefing: InterpretedBriefing dict for context.

    Returns:
        Complete prompt string.
    """
    slides_json = json.dumps(slides, ensure_ascii=False, indent=2)
    briefing_json = json.dumps(briefing, ensure_ascii=False, indent=2)

    return f"""\
You are a Design-Reviewer for business presentations.

TASK:
Review the complete slide deck for quality, coherence, and audience fit.
Identify issues and produce a QualityReport.

BRIEFING:
{briefing_json}

SLIDES:
{slides_json}

REVIEW CRITERIA:

1. FACT SAFETY (HIGHEST PRIORITY)
   - Are there any invented numbers, percentages, KPIs, dates, or metrics?
   - Every number must be traceable to the briefing input.
   - If a slide claims a specific improvement ("+15%", "3x faster"), verify it exists in the briefing.
   - Unverifiable facts = severity "error", auto_fixable true (replace with qualitative statement).
   - Generic AI filler language ("revolutionizing", "transformative", "game-changing") = severity "warning".

2. NARRATIVE COHERENCE
   - Does the deck tell a logical story from opening to closing?
   - Are transitions between slides smooth?
   - Does each headline advance the narrative (not just label a topic)?

3. AUDIENCE FIT
   - Is the tone appropriate for the target audience?
   - Is content density right? (Management = sparse, Team = moderate)
   - For management: does every bullet have a bold_prefix?

4. HEADLINE QUALITY
   - Headlines must be statements, not labels.
   - Max 70 characters each.
   - No two headlines should say the same thing.

5. REDUNDANCY
   - Flag any two slides that cover the same content.
   - Flag repeated phrases across headlines.
   - Flag identical bullet points.

6. STRUCTURAL RULES
   - First slide must be title_hero, last must be closing.
   - No two consecutive bullets_focused slides.
   - kpi_dashboard: exactly 3-4 KPIs.
   - three_cards: exactly 3 cards.
   - comparison: exactly 2 columns.
   - timeline: 3-6 entries.
   - process_flow: 3-5 steps.

7. CHARACTER LIMITS
   - headline: max 70, subheadline: max 120, core_message: max 150
   - bullet text: max 80, bold_prefix: max 25
   - speaker_notes: max 600
   - Check all content_block limits per type.

8. TEMPLATE COMPLIANCE
   - Does each slide respect the template's visual language?
   - Are colors from the approved palette only?
   - Is the content density appropriate for the chosen layout?
   - Would the slide look native to the master deck, not pasted on top?

9. CREDIBILITY CHECK
   - Would an executive believe every statement is source-backed?
   - Is there any hyperbolic or inflated language?
   - Are placeholder texts or generic filler still present?

REPAIR PRIORITY (for auto_fixable issues):
1. Remove invented/unverified facts (replace with qualitative statement)
2. Fix template or layout misuse
3. Fix overcrowding by shortening content
4. Remove generic AI filler language
5. Fix redundancy

SEVERITY:
- "error": Must be fixed before rendering. Deck will break or credibility will suffer if ignored.
- "warning": Should be fixed for quality but won't break rendering.

OUTPUT SCHEMA (QualityReport):
{{
  "overall_score": "float 0-100 — deduct 10 per error, 3 per warning",
  "passed": "boolean — true if overall_score >= 70 AND zero errors",
  "deck_findings": [
    {{
      "rule": "string — rule identifier e.g. 'narrative_coherence'",
      "severity": "error | warning",
      "message": "string — human-readable description",
      "auto_fixable": "boolean",
      "slide_index": null
    }}
  ],
  "slide_findings": [
    {{
      "slide_index": "int — 0-based index",
      "findings": [
        {{
          "rule": "string",
          "severity": "error | warning",
          "message": "string",
          "auto_fixable": "boolean",
          "slide_index": "int"
        }}
      ],
      "regenerate": "boolean — true if errors are too severe to auto-fix"
    }}
  ]
}}

Output ONLY valid JSON matching the schema above. No markdown fences, no explanation text."""
