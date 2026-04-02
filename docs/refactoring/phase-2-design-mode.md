# Phase 2 — Design Mode with HTML-First Rendering

**Duration:** Week 3-4
**Goal:** Create the TypeScript rendering service with visual preview, replacing static python-pptx blueprints with dynamic HTML-based rendering and PptxGenJS export.

---

## Context

The current V2 design mode uses static blueprints with fixed cm coordinates (see [v2-pipeline-issues.md](v2-pipeline-issues.md), Issue 2) that cannot adapt to content volume. Phase 2 introduces a TypeScript rendering service that renders slides as HTML first (for preview and quality review) and then exports to PPTX via PptxGenJS.

---

## Tasks

### 1. Set up TypeScript render service

**Directory:** `rendering-service/`

Initialize a new Node.js project:
- TypeScript 5.x with strict mode
- React 19 for component rendering (server-side only)
- Tailwind CSS 4.x for styling
- Express.js for HTTP API
- Puppeteer for screenshot generation
- PptxGenJS for PPTX export

```
rendering-service/
  src/
    components/         # React layout components
    renderer/           # Server-side rendering logic
    screenshots/        # Puppeteer pipeline
    export/             # PptxGenJS export
    api/                # Express routes
    types/              # Shared TypeScript types
  package.json
  tsconfig.json
  Dockerfile
```

### 2. Create layout family React components

**Directory:** `rendering-service/src/components/`

Build 7 layout family components:

| Component | Layout Family | Key Features |
|---|---|---|
| `HeroSlide` | HERO | Full-bleed background, centered title + subtitle |
| `SectionDividerSlide` | SECTION_DIVIDER | Minimal, large title, optional accent |
| `TimelineSlide` | TIMELINE | Horizontal or vertical timeline with up to 5 nodes |
| `CardGridSlide` | CARD_GRID | 2-4 cards with icon/text, responsive grid |
| `ComparisonSlide` | COMPARISON | Side-by-side columns with headers |
| `KeyFactSlide` | KEY_FACT | Prominent assertion + supporting bullets |
| `ClosingSlide` | CLOSING | CTA text, contact info, subtle background |

Each component must:
- Accept a `CompressedSlideSpec` as props
- Render at exactly 1920x1080 pixels (16:9)
- Use Tailwind classes for all styling
- Support theme customization (colors, fonts)

### 3. Create server-side slide preview renderer

**File:** `rendering-service/src/renderer/slide_renderer.ts`

Implement server-side React rendering:
- `renderSlideToHtml(spec: CompressedSlideSpec, theme: ThemeConfig): string`
- Produces a self-contained HTML document (inline styles, embedded fonts)
- Includes Tailwind output as inline CSS
- Returns complete HTML ready for Puppeteer

### 4. Set up Puppeteer screenshot pipeline

**File:** `rendering-service/src/screenshots/screenshot_pipeline.ts`

Implement screenshot capture:
- `captureSlideScreenshot(html: string): Promise<Buffer>`
- Renders HTML at 1920x1080 viewport
- Captures PNG screenshot
- Returns image buffer for quality review
- Manages Puppeteer browser lifecycle (pool for concurrent captures)

### 5. Create PptxGenJS export module

**File:** `rendering-service/src/export/pptx_exporter.ts`

Implement PPTX generation:
- `exportDeckToPptx(specs: CompressedSlideSpec[], theme: ThemeConfig): Promise<Buffer>`
- Maps each layout family to PptxGenJS slide definitions
- Translates Tailwind visual properties to PPTX equivalents (colors, fonts, spacing)
- Handles images (embed from URLs or base64)
- Handles charts (embed as images from pre-rendered matplotlib output)
- Produces valid PPTX with correct slide dimensions (10" x 7.5")

### 6. Create visual review engine

**File:** `rendering-service/src/renderer/visual_review.ts`

Implement screenshot-based quality scoring:
- `reviewSlide(screenshot: Buffer): Promise<ReviewResult>`
- Rule-based scoring dimensions:
  - Text density: calculate approximate text area vs total slide area
  - Whitespace balance: check margins and padding
  - Element count: flag slides with too many distinct elements
  - Font size consistency: verify no text below minimum threshold
- Optional: send screenshot to Gemini Vision for holistic score
- Returns `ReviewResult { score: number, passed: boolean, failures: string[] }`

### 7. Wire Python orchestrator to TypeScript render service

**File:** `pptx-service/app/pipeline/orchestrator.py` (modify existing)

Add HTTP calls to the rendering service:
- After Stage 6 (Layout), call `POST /api/v1/render-preview` with `PlannedSlideSpec[]`
- Receive screenshots and review scores
- If any slide fails review, trigger replan engine (from Phase 1)
- After all slides pass, call `POST /api/v1/render-export` for final PPTX

### 8. Create preview endpoint

**File:** `rendering-service/src/api/routes/preview.ts`

`POST /api/v1/render-preview`
- Request body: `{ slides: PlannedSlideSpec[], theme: ThemeConfig }`
- Response: `{ slides: [{ html: string, screenshot: base64, review: ReviewResult }] }`
- Renders each slide, captures screenshot, runs review
- Returns all results in a single response

### 9. Create export endpoint

**File:** `rendering-service/src/api/routes/export.ts`

`POST /api/v1/render-export`
- Request body: `{ slides: PlannedSlideSpec[], theme: ThemeConfig }`
- Response: PPTX file as binary stream
- Generates complete deck via PptxGenJS
- Sets proper content-type and disposition headers

---

## Acceptance Criteria

- [ ] Each of the 7 layout family components renders correctly at 1920x1080 with sample data.
- [ ] Screenshots are visually identical to the HTML preview (no rendering artifacts).
- [ ] PptxGenJS output opens correctly in PowerPoint, Google Slides, and LibreOffice Impress.
- [ ] Visual review scores correlate with human judgment on a test set of 30 slides (Spearman r > 0.7).
- [ ] Python orchestrator successfully calls the rendering service and handles errors gracefully.
- [ ] Preview endpoint responds within 3 seconds per slide.
- [ ] Export endpoint produces a valid PPTX file for decks up to 30 slides.
- [ ] Rendering service has a Dockerfile and integrates into `docker-compose.yml`.

---

## Files Created

| File | Purpose |
|---|---|
| `rendering-service/` | New Node.js service (entire directory) |
| `rendering-service/src/components/*.tsx` | 7 layout family React components |
| `rendering-service/src/renderer/slide_renderer.ts` | Server-side HTML rendering |
| `rendering-service/src/screenshots/screenshot_pipeline.ts` | Puppeteer screenshot capture |
| `rendering-service/src/export/pptx_exporter.ts` | PptxGenJS PPTX export |
| `rendering-service/src/renderer/visual_review.ts` | Screenshot-based quality scoring |
| `rendering-service/src/api/routes/preview.ts` | Preview endpoint |
| `rendering-service/src/api/routes/export.ts` | Export endpoint |

## Files Modified

| File | Change |
|---|---|
| `pptx-service/app/pipeline/orchestrator.py` | Add HTTP calls to rendering service |
| `docker-compose.yml` | Add rendering-service container |
