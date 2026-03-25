"""Input Interpreter prompt — parses user input into InterpretedBriefing JSON."""

from __future__ import annotations


_INTERPRETED_BRIEFING_SCHEMA = """\
{
  "topic": "string — Main topic of the presentation (required)",
  "goal": "string — Presentation goal in one sentence (required)",
  "audience": "enum: management | team | customer | workshop (default: management)",
  "tone": "enum: formal_analytical | persuasive | collaborative | educational (default: formal_analytical)",
  "image_style": "enum: photo | illustration | minimal | data_visual | none (default: minimal)",
  "requested_slide_count": "integer 5..25 (default: 10)",
  "key_facts": ["string — extracted key facts, numbers, data points"],
  "content_themes": ["string — identified thematic clusters"],
  "constraints": {
    "must_include": ["string — topics/elements the user explicitly wants"],
    "must_avoid": ["string — topics/elements to exclude"],
    "language": "string — ISO language code (default: de)"
  },
  "needs_clarification": "boolean — true if the input is too vague to produce a good deck",
  "clarification_questions": ["string — questions to ask, only if needs_clarification is true"]
}"""


def build_interpreter_prompt(user_input: str, document_text: str = "") -> str:
    """Build the Input Interpreter prompt.

    Args:
        user_input: Raw user prompt text.
        document_text: Optional extracted text from uploaded documents.

    Returns:
        Complete system + user prompt string.
    """
    document_section = ""
    if document_text:
        document_section = f"""

--- HOCHGELADENES DOKUMENT ---
{document_text}
--- ENDE DOKUMENT ---
"""

    return f"""\
You are a Briefing-Analyst for business presentations.

TASK:
Analyze the user input (and optional document text) and produce a structured
InterpretedBriefing as JSON. Extract every fact, number, and constraint.
Infer audience, tone, and image_style from context clues when not stated explicitly.

RULES:
1. If the user specifies a slide count, use it. Otherwise default to 10.
2. Extract ALL numbers, percentages, dates, and proper nouns into key_facts.
3. Group related topics into content_themes (3-7 themes for a typical deck).
4. Set needs_clarification to true ONLY if the input is genuinely too vague
   (fewer than 2 sentences AND no document text).
5. Always set language to "de" unless the user explicitly writes in English.
6. audience defaults to "management" if not clear from context.
7. image_style: if the user mentions charts/data → "data_visual",
   if they mention photos → "photo", otherwise → "minimal".
8. Detect if the topic is historical, biographical, or chronological in nature.
   Set a content_theme "chronological" or "historical" if the topic involves
   development over time, eras, epochs, or historical progression.
9. Extract temporal markers: dates, centuries, eras, "before/after" patterns.
   Add them to key_facts with their context.
10. If the topic naturally suggests a timeline or development arc,
    add "timeline" and "development" to content_themes.

OUTPUT SCHEMA (InterpretedBriefing):
{_INTERPRETED_BRIEFING_SCHEMA}

--- USER INPUT ---
{user_input}
{document_section}
--- ENDE ---

Output ONLY valid JSON matching the schema above. No markdown fences, no explanation text."""
