# ADR-001: Two Rendering Modes (Design + Template)

**Status:** Accepted  
**Date:** 2026-04-02  
**Decision Makers:** Architecture Team

## Context

The platform needs to serve two fundamentally different use cases:

1. **Creative presentations** — users want visually striking, magazine-quality slides with modern layouts, gradients, and dynamic compositions. No corporate template constraints.
2. **Corporate presentations** — users have an existing `.pptx` template with mandated colors, fonts, logos, and layouts. The output must look like it was made by hand in that template.

A single rendering path cannot serve both well. Creative rendering requires expressive layout freedom (HTML/CSS-level control), while template rendering requires strict adherence to existing placeholder geometry and style rules.

## Decision

Implement two distinct render modes, selected per presentation:

### Design Mode (`render_mode: "design"`)
- AI-designed layouts with full creative freedom
- HTML/CSS-first rendering in a headless browser, then converted to editable PPTX
- No template constraints — the system IS the designer
- Tech: PptxGenJS for programmatic PPTX construction

### Template Mode (`render_mode: "template"`)
- Uses an uploaded corporate `.pptx` as the base
- Deterministic placement into existing placeholders
- Preserves template masters, color scheme, font scheme
- Tech: pptx-automizer for cloning/filling template layouts

### Shared Contract
Both modes consume the same `PresentationSpec` domain model. The `render_mode` field on the spec (and per-slide override) determines which renderer processes each slide.

## Consequences

### Positive
- Each mode can be optimized independently without compromising the other
- Template mode can guarantee pixel-perfect corporate compliance
- Design mode can push creative boundaries without template limitations
- Clear separation of concerns in the codebase

### Negative
- Two rendering paths to maintain and test
- Slide type support must be implemented twice (once per renderer)
- More complex deployment (both renderers must be available)

### Risks
- Feature drift between modes if not kept in sync via shared PresentationSpec
- Mitigated by: shared domain model, shared validation, shared quality gate
