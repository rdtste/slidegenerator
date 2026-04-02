# ADR-002: Mandatory Content Compression Before Layout and Rendering

**Status:** Proposed
**Date:** 2026-04-02

## Context

The V2 pipeline lets the LLM generate content freely during Stage 5 (Content Filling) and then tries to fix overflow issues via truncation and auto-fixes in later stages. This produces slides that are "formally correct but inelegant" -- content-filled containers instead of designed presentations. Text gets crammed into available space, bullet points multiply unchecked, and the result reads like a document pasted onto slides rather than a visual presentation.

The root cause is that content is never reduced to its essence before rendering. The pipeline expands content first and then tries to constrain it, which is fundamentally backwards. Truncation preserves the beginning of text but not necessarily the most important parts. Auto-fixes adjust font sizes and spacing but cannot improve the underlying content density.

## Decision

Introduce a mandatory Content Compression stage between Presentation Strategy and Layout Selection. This stage enforces the principle that every slide should communicate one idea clearly, not many ideas densely.

The Content Compression stage will:

1. **Extract one core assertion per slide** -- the single sentence that captures what the audience should remember.
2. **Limit supporting details to hard budgets** -- word counts (not character counts) per layout zone. Word counts better reflect cognitive load than character counts.
3. **Remove filler words and redundant qualifiers** -- semantic compression via LLM, not mechanical truncation.
4. **Enforce one dominant element per slide** -- if a slide has both a chart and a large text block, one must be primary and the other subordinate.
5. **Auto-split slides that exceed budgets after compression** -- if compressed content still exceeds the word budget, the slide is split into two slides rather than being crammed into one.
6. **Use LLM for semantic compression** -- the LLM is instructed to reduce content to its essence, preserving meaning while cutting volume. This is fundamentally different from truncation, which cuts arbitrarily.

Word budgets per zone (indicative):
- Slide title: 8 words max
- Subtitle: 12 words max
- Bullet point: 15 words max
- Bullets per slide: 5 max
- Body text block: 40 words max
- Card text: 20 words max

## Consequences

- Slides will have less text but higher impact. Presenters will need to speak to the content rather than read from it.
- The LLM is used for compression (reducing), not for filling (expanding). This reverses the current pattern where the LLM is encouraged to elaborate.
- Hard word budgets per layout zone replace soft character limits. Budgets are enforced mechanically after LLM compression.
- Some user-provided content may be significantly shortened. The original content should be preserved in speaker notes.
- The compression stage adds one LLM call per slide, increasing latency and cost. This is justified by the quality improvement.
- Content splitting means the final deck may have more slides than the user requested. This is preferable to fewer, overcrowded slides.

## Alternatives Considered

- **Post-render truncation (current approach):** Let content overflow and fix it after rendering. Rejected because truncation cannot improve content quality, only reduce its quantity arbitrarily.
- **Strict input validation:** Reject user input that is too long. Rejected because users should be free to provide detailed briefs; it is the system's job to distill them.
- **Font size reduction:** Shrink text to fit. Rejected because small text on slides defeats the purpose of a presentation and signals poor design.
- **Layout-aware generation:** Have the LLM generate content with layout constraints in mind. Partially adopted (the LLM receives word budgets), but compression is still needed as a safety net because LLMs do not reliably respect token budgets.
