# Current State Architecture

## Overview

Three microservices deployed on Google Cloud Run as multi-container setup.

```
[Frontend: Angular 21]  →  [Backend: NestJS 11]  →  [PPTX Service: FastAPI]
     :4200                     :3000 (API GW)           :8000 (sidecar)
                                    ↓
                            [Vertex AI Gemini]
```

## Service Responsibilities

### Frontend (Angular 21)
- Chat-based briefing UI
- Slide preview (card view)
- Export controls (V1 Markdown, V2 AI Pipeline)
- Template management UI (upload, scope, delete)
- State: `ChatState` injectable with Angular Signals

### Backend (NestJS 11)
- API Gateway (`/api/v1/*`)
- Chat orchestration ("Clarity Engine" — Gemini-based multi-turn briefing)
- Export job management (async SSE-based progress tracking)
- Template CRUD + sync to pptx-service
- Preview generation (Marp-based)
- Proxies to PPTX Service for generation

### PPTX Service (FastAPI)
- PPTX generation (V1 + V2 pipelines)
- Template management (upload, listing, profiling)
- Image generation (Vertex AI Imagen 3.0)
- Chart generation (matplotlib)
- Visual QA (LibreOffice → PDF → JPEG → Gemini Vision)
- Template profiling (Color DNA, Typography DNA, Layout analysis)

## Two Generation Pipelines

### V1 Pipeline (Markdown-based)
```
Gemini Chat → Markdown → parse_markdown() → generate_pptx()
                              ↓
                    SlideContent (7 layout types)
                              ↓
                    Template layout resolution (keyword scoring)
                              ↓
                    Placeholder-based filling
```
- Layout types: title, section, content, two_column, image, chart, closing
- Uses template placeholders directly (TITLE, BODY, OBJECT, PICTURE)
- Template analysis via .analysis.json (AI-generated layout mapping)
- Scored keyword matching as fallback for layout resolution

### V2 Pipeline (AI-driven, 8 stages)
```
Stage 1: Input Interpreter (LLM → InterpretedBriefing)
Stage 2: Storyline Planner (LLM → Storyline with StoryBeats)
Stage 3: Slide Planner (LLM → PresentationPlan with SlidePlans)
Stage 4: Schema Validator (Code → auto-fixes + LLM regeneration)
Stage 5: Content Filler (LLM per slide → FilledSlide with TextMetrics)
Stage 6: Layout Engine (Code → RenderInstruction via Blueprints)
Stage 7: PPTX Renderer (Code → python-pptx shapes and textboxes)
Stage 8: Design Review (Gemini Vision QA → programmatic fixes)
```
- 14 slide types with rich content model
- Blueprint-based layout system (deterministic positions)
- Adds shapes/textboxes directly (does NOT use template placeholders)
- Hardcoded layout map for REWE template (`_REWE_LAYOUT_MAP`)

## Template System

### Template Profiling (profile_service.py)
Extracts from template OOXML:
- ColorDNA: scheme colors (accent1-6), chart color sequence
- TypographyDNA: heading/body fonts, sizes
- Layout catalog: per-layout placeholder details (type, position, size)
- Chart/Image guidelines
- Supported layout types

### Template Storage
- Filesystem-based (shared via GCS FUSE in production)
- `.meta.json` per template (scope, sessionId, uploadedAt)
- `.profile.json` per template (deep analysis result)
- `.analysis.json` per template (AI layout classification)

## Data Models

### V2 Pipeline Schemas (well-structured)
- `InterpretedBriefing` — parsed user intent
- `Storyline` / `StoryBeat` — narrative structure
- `PresentationPlan` / `SlidePlan` — slide-level planning
- `FilledSlide` / `TextMetrics` — finalized content
- `RenderInstruction` / `RenderElement` — pixel-precise rendering
- `QualityReport` — validation results
- 9 content block types (Bullets, KPI, Quote, Card, etc.)

### Template Profile Models
- `TemplateProfile` — comprehensive profile
- `ColorDNA`, `TypographyDNA` — visual identity
- `LayoutDetail`, `PlaceholderDetail` — layout structure
- `ChartGuidelines`, `ImageGuidelines` — generation hints

## Deployment
- Cloud Run multi-container: backend (ingress) + pptx-service (sidecar)
- GCS FUSE volume for shared templates
- Custom internal domain (*.internal.run.rewe.cloud)
- VPC connector for egress

## Identified Strengths
1. Rich V2 content model with 14 slide types
2. Deterministic layout engine (no LLM for positions)
3. Deep template profiling (Color DNA, Typography DNA)
4. Visual QA loop (Gemini Vision)
5. SSE-based progress streaming
6. Robust V1 template placeholder filling

## Identified Weaknesses
1. V1/V2 are disconnected — no shared content model
2. V2 renderer ignores template placeholders
3. Template profiling data is not used by V2 renderer
4. Hardcoded REWE layout map
5. No template versioning
6. No explicit mode concept (Design vs Template)
7. In-memory job and file storage
8. Blueprint positions don't adapt to template dimensions
