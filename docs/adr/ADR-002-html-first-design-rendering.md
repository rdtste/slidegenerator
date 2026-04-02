# ADR-002: HTML-first Design Rendering

**Status:** Accepted  
**Date:** 2026-04-02  
**Decision Makers:** Architecture Team

## Context

The current python-pptx rendering approach builds slides programmatically by placing shapes, text frames, and images at computed positions. This has significant limitations:

- Complex layouts (gradients, rounded cards, overlapping elements) are extremely difficult
- Typography control is limited (no CSS-like flexbox, grid, or responsive sizing)
- Visual quality depends on precise coordinate math that's fragile and hard to maintain
- No WYSIWYG preview — the rendered PPTX is the first time anyone sees the design
- Content leaks (raw descriptors, icon hints as text) happen because the renderer has no visual awareness

Modern web technologies (HTML, CSS, Tailwind) offer vastly superior layout capabilities, and headless browsers can render them to pixel-perfect images or convertible DOM structures.

## Decision

For **Design Mode**, adopt an HTML-first rendering pipeline:

1. **Slide → HTML/CSS**: Each slide type has a TypeScript component that renders the `SlideSpec` as styled HTML (React + Tailwind)
2. **Browser Render**: Headless Chromium renders each slide at 1920x1080 (or presentation dimensions)
3. **DOM → PPTX**: Convert the rendered DOM to editable PPTX elements using PptxGenJS, preserving text editability where possible
4. **Fallback**: For elements that can't be converted to editable PPTX shapes, embed as high-resolution background images with editable text overlays

### Technology Stack
- **PptxGenJS** — programmatic PPTX generation in TypeScript/Node
- **Headless Chromium** (Puppeteer) — browser rendering for visual fidelity
- **React + Tailwind** — component-based slide templates with utility-first CSS

### Rendering Service
A new TypeScript/Node **rendering-service** handles all visual rendering. The Python pptx-service remains responsible for API orchestration, LLM pipeline, and content intelligence.

## Consequences

### Positive
- Pixel-perfect visual quality matching modern design tools
- CSS layout capabilities (flexbox, grid, gradients, shadows, rounded corners)
- Browser-based preview matches final output exactly
- Large ecosystem of web design tools and libraries
- TypeScript type safety for the rendering pipeline

### Negative
- Requires headless browser in production (memory/CPU overhead)
- DOM-to-PPTX conversion is lossy for some CSS features
- Added service complexity (Python + Node in the pipeline)

### Alternatives Considered
- **python-pptx only**: Current approach, hit its ceiling for visual quality
- **PptxGenJS only (no browser)**: Better than python-pptx but still limited for complex layouts
- **PDF export only**: Would lose PPTX editability, a hard requirement
