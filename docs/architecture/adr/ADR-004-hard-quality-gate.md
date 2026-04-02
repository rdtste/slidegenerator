# ADR-004: Hard Quality Gate -- No Bad Slides in Final Export

**Status:** Proposed
**Date:** 2026-04-02

## Context

The V2 pipeline has a Preflight scoring system (0-100 per slide) but it is configured as warning-only: a score below 70 logs a warning and continues rendering. The Design Review Agent in Stage 8 also only attempts minor fixes (font size, spacing). The result is that knowingly mediocre slides are exported to the user.

This "best effort" approach undermines user trust. A single badly composed slide in a 20-slide deck makes the entire deck feel unpolished. Users who receive a poor slide will not think "the AI tried its best" -- they will think "this tool produces bad output."

The current pipeline treats quality as an observation ("this slide scored 45") rather than a constraint ("this slide must score at least 70 to be exported"). Quality must become a hard gate, not an advisory metric.

## Decision

Introduce a hard quality gate between Preview Composition and Final Render. No slide may be exported unless it passes a minimum quality threshold.

**Gate rules:**

1. Every slide must achieve a quality score of 70 or above (on a 0-100 scale).
2. Slides below threshold trigger automatic replanning with the following escalation chain:
   - **First:** Reduce content -- remove the lowest-priority supporting details and re-score.
   - **Second:** Try an alternative layout from the same layout family (e.g., swap `bullets_focused` for `key_statement`).
   - **Third:** Split into two slides -- divide the content across two simpler slides.
   - **Fourth:** Escalate -- log an error, include the slide with a warning flag in metadata. This is the failure case and should be rare.
3. Maximum 2 replan iterations per slide to prevent infinite loops and bound latency.
4. The gate applies to both Design Mode and Template Mode. Template Mode uses a simplified scoring model (readability + completeness only).
5. Deck-level review (overall flow, consistency, pacing) runs after individual slide gates. Deck-level issues are advisory -- they can flag concerns but do not block export.

**Quality dimensions scored:**

| Dimension     | Weight | What it measures                                      |
|---------------|--------|-------------------------------------------------------|
| Readability   | 30%    | Text density vs. available space, font size adequacy  |
| Hierarchy     | 25%    | Clear dominant element, visual weight distribution    |
| Balance       | 20%    | Content block consistency, whitespace distribution    |
| Completeness  | 15%    | All required elements present (title, visual, etc.)   |
| Visual Fit    | 10%    | Appropriate visual for slide intent and content       |

## Consequences

- Some slides will be simpler than what the LLM originally planned. This is intentional -- "less is more" is the core design principle.
- Worst case: a slide is split into two simpler slides rather than one crowded slide. The deck may end up with more slides than requested, but each slide will meet the quality bar.
- The replan loop adds latency (up to 2 additional LLM calls per failing slide). For most slides this will not trigger; for problematic slides, the latency is justified by the quality improvement.
- The escalation chain ensures the system always produces output -- it never blocks indefinitely. The fourth step (escalate with warning) is the escape hatch.
- Template Mode scoring is simpler because template layouts are pre-designed; the gate only needs to verify that content fits the placeholders and is readable.
- Quality thresholds may need tuning after deployment. The 70-point threshold is a starting point based on current Preflight scoring distribution.

## Alternatives Considered

- **Warning-only scoring (current approach):** Log quality scores but always export. Rejected because it allows known-bad slides to reach users, undermining trust.
- **User-facing quality report:** Show quality scores to users and let them decide whether to download. Rejected because most users cannot interpret quality scores and should not need to. The system should guarantee minimum quality.
- **Reject and regenerate entire deck:** If any slide fails, regenerate the full deck. Rejected because it wastes good slides and increases latency dramatically. Per-slide replanning is more efficient.
- **Higher threshold (e.g., 85):** Set a stricter quality bar. Rejected as an initial target because it would cause too many replan loops with current content generation quality. The threshold can be raised as the pipeline matures.
