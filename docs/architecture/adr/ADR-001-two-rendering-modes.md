# ADR-001: Separate Design Mode and Template Mode as Independent Rendering Pipelines

**Status:** Proposed
**Date:** 2026-04-02

## Context

The current V2 pipeline tries to handle both creative design and corporate template filling in the same code path. Design Mode needs visual composition freedom (HTML-first, preview-based), while Template Mode needs deterministic reliability (placeholder mapping, no creative interpretation). Mixing them leads to compromises in both: creative slides are constrained by template logic, and template slides are destabilized by creative heuristics.

The shared rendering path forces layout selection, content placement, and visual review to accommodate two fundamentally different goals. This results in code that is harder to maintain, harder to test, and produces mediocre output for both use cases.

## Decision

Introduce a `RenderMode` enum with two values: `DESIGN` and `TEMPLATE`. Each mode gets its own rendering pipeline that diverges after the shared planning stages.

**Shared stages (both modes):**
- Presentation Request parsing
- Presentation Plan / Storyline generation
- Content generation and compression

**Design Mode pipeline:**
- HTML/React/Tailwind slide composition
- Browser-based visual preview
- Visual Quality Gate on screenshot
- PPTX export via PptxGenJS or dom-to-pptx bridge

**Template Mode pipeline:**
- Template descriptor lookup (pre-analyzed at upload time)
- Deterministic placeholder mapping
- pptx-automizer for reliable template filling
- Mechanical overflow handling (truncate/split)

Both pipelines share the same domain models (`PresentationRequest`, `PresentationPlan`, `SlideContent`) but diverge at the composition and rendering layers.

## Consequences

- Two rendering pipelines to maintain, each with its own tests and deployment considerations.
- Shared domain model prevents the pipelines from diverging at the data level.
- Template Mode becomes simpler and more reliable by shedding creative interpretation logic.
- Design Mode can evolve independently, adopting new visual techniques without risking template stability.
- Users get a clear mental model: "Design Mode = creative freedom, Template Mode = brand compliance."
- The orchestrator must route to the correct pipeline based on mode selection, adding a branching point early in the flow.

## Alternatives Considered

- **Single pipeline with feature flags:** Keep one rendering path and use flags to toggle behavior. Rejected because the conditional logic would grow unmanageably and make both paths harder to reason about.
- **Template Mode only:** Drop creative design and focus solely on template filling. Rejected because users without corporate templates need a way to generate visually appealing slides from scratch.
- **Design Mode only:** Use creative rendering for everything, including templates. Rejected because corporate users need deterministic, predictable output that matches their brand guidelines exactly.
