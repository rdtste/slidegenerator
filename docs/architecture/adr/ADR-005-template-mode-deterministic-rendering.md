# ADR-005: Deterministic Template Rendering Without Creative Interpretation

**Status:** Proposed
**Date:** 2026-04-02

## Context

The current template-based rendering (V1) uses scored keyword matching and AI analysis to map content to template layouts. While functional, it sometimes makes wrong layout choices, and the rendering quality depends on how well the AI guessed the template structure. Corporate users need predictable, reliable results when using their own branded templates.

The AI-based layout matching introduces non-determinism: the same template and the same content can produce different layout selections across runs. This makes debugging difficult and erodes user confidence. When a corporate user uploads their company's branded template, they expect the output to look exactly like slides produced by their design team -- not "close enough."

Additionally, the current approach re-analyzes template structure at render time, which is wasteful. Template structure does not change between renders; it only changes when the template file itself is updated.

## Decision

Template Mode rendering must be fully deterministic. No AI interpretation occurs at render time. All intelligence is front-loaded to template upload time.

**Template analysis (at upload time):**

1. When a template is uploaded, it is analyzed once to produce a `TemplateDescriptor`.
2. The descriptor contains explicit placeholder mappings: which placeholder accepts which content type (title, body, bullets, picture, chart).
3. The descriptor includes layout metadata: available layouts, their placeholder configurations, and content capacity (word limits per placeholder).
4. The descriptor is stored as `.descriptor.json` alongside the template file.
5. Template versioning: each template gets a content hash. Re-analysis is triggered only when the hash changes (template file updated).

**Rendering (at generation time):**

1. Content is mapped to placeholders by type: title content goes to title placeholders, bullets go to body placeholders, images go to picture placeholders.
2. No AI interpretation of layout names at render time. Layout selection is based on content shape (number of content elements and their types) matched against the descriptor's layout configurations.
3. Overflow handling is mechanical:
   - Text exceeding placeholder capacity is truncated at the nearest word boundary.
   - If content cannot fit in any single slide layout, it is split to the next slide.
   - Font sizes are never reduced below the template's defined minimum.
4. Technology: **pptx-automizer** for reliable placeholder access and master slide inheritance. This library provides better placeholder handling than raw python-pptx for template-based workflows.

**Placeholder mapping rules:**

| Placeholder Type | Content Mapped           | Overflow Behavior              |
|------------------|--------------------------|--------------------------------|
| Title            | Slide headline           | Truncate to fit                |
| Body / Object    | Bullets or body text     | Truncate, then split to next   |
| Picture          | Generated or provided image | Scale to fit, maintain aspect |
| Chart            | Chart from chart_spec    | Render at placeholder size     |
| No match         | --                       | Skip content, log warning      |

## Consequences

- Template Mode output will look like the template designer intended. Corporate branding is preserved exactly.
- Less creative freedom compared to Design Mode, but much higher reliability. This is the correct trade-off for corporate use cases.
- Template analysis at upload time adds a one-time cost (one LLM call + structural analysis) but eliminates per-render AI costs.
- The `.descriptor.json` format becomes a contract between template analysis and rendering. Changes to this format require migration of existing descriptors.
- Templates with unusual or non-standard placeholder configurations may produce suboptimal results. The descriptor format should support manual override for edge cases.
- pptx-automizer handles master slide inheritance correctly, which resolves current issues where template styles (fonts, colors) are lost during rendering.
- Debugging becomes straightforward: given a template descriptor and content input, the output is fully predictable.

## Alternatives Considered

- **AI-based layout matching at render time (current approach):** Use scored keyword matching and Gemini analysis to select layouts. Rejected because it introduces non-determinism and sometimes selects wrong layouts, which is unacceptable for corporate templates.
- **Manual placeholder tagging UI:** Require users to manually tag placeholders in their templates via a web UI. Rejected because it adds friction to the upload process and most users will not understand placeholder concepts.
- **Hybrid approach (AI-assisted deterministic):** Use AI for initial descriptor generation but allow manual corrections. Partially adopted -- the descriptor is AI-generated at upload time but can be manually edited. At render time, only the descriptor is used (no AI).
- **python-pptx with improved heuristics:** Keep python-pptx but improve the placeholder detection logic. Rejected because python-pptx's placeholder API has fundamental limitations with complex templates (grouped shapes, nested placeholders, custom XML).
