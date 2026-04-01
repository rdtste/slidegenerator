# ADR-002: Direct python-pptx Rendering (No HTML Intermediate)

## Status
Accepted

## Date
2026-04-01

## Context
We evaluated three rendering approaches:
1. Direct PPTX rendering via python-pptx
2. HTML/React/Tailwind intermediate → PPTX conversion
3. Hybrid (HTML for preview, python-pptx for final output)

## Decision
**Direct python-pptx rendering** for both Design Mode and Template Mode.

### Rationale
1. **PPTX is the target format** — An intermediate format doubles complexity without adding value
2. **HTML→PPTX conversion is lossy** — No reliable tool converts HTML layouts to OOXML faithfully
3. **Corporate templates are OOXML-native** — Their placeholders, styles, master slides are defined in OOXML; HTML cannot represent them
4. **python-pptx provides full control** — Font sizing, positioning, shapes, images, charts at sub-millimeter precision
5. **"Gamma-like quality" is a design problem, not a rendering problem** — Better spacing, typography hierarchy, and theme integration achieve visual excellence within python-pptx

### Two Renderers
- **DesignModeRenderer** — Builds slides using textboxes, shapes, and images positioned by the Blueprint/Layout system. Theme-aware colors and fonts.
- **TemplateModeRenderer** — Fills template placeholders (TITLE, BODY, OBJECT, PICTURE) using analyzed PlaceholderMapping. Respects template-defined styles.

Both implement the `PresentationRenderer` protocol and share typography utilities.

## Consequences
- No dependency on browser rendering engines or headless Chrome
- Template Mode can guarantee template integrity (only fills existing placeholders)
- Design Mode can push visual boundaries within python-pptx capabilities
- Preview rendering remains separate (existing Marp-based preview or slide cards)

## Alternatives Rejected
- **HTML intermediate**: Too complex, lossy conversion, cannot handle PPTX templates
- **pptxgenjs (JavaScript)**: Less mature than python-pptx, weaker template support
- **LibreOffice SDK**: Too heavy for Cloud Run, complex API
