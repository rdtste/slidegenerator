# Phase 1 — Domain Foundation & Content Compression

**Duration:** Week 1-2
**Goal:** Establish shared domain models and the content compression module, wired into the existing V2 pipeline as a non-breaking enhancement.

---

## Context

The V2 pipeline generates content without word budgets (see [v2-pipeline-issues.md](v2-pipeline-issues.md), Issue 1) and uses a weak quality gate that warns but does not block (Issue 3). Phase 1 addresses both problems by introducing domain models with explicit budgets and a compression step that enforces them.

---

## Tasks

### 1. Create domain models

**File:** `pptx-service/app/domain/models.py`

Define the following Pydantic models:

- `PresentationRequest` — user input (topic, audience, tone, slide count, template reference, render mode)
- `PresentationPlan` — ordered list of slide intents with layout family assignments
- `SlideSpec` — raw LLM-generated content for a single slide (title, subtitle, body, bullets, visual_prompt, chart_data)
- `CompressedSlideSpec` — post-compression content with verified word counts
- `PlannedSlideSpec` — compressed content + resolved layout coordinates + visual assets
- `RenderMode` — enum: `DESIGN`, `TEMPLATE`

### 2. Create layout families with budgets

**File:** `pptx-service/app/domain/layout_families.py`

Define 7 layout families with hard word budgets per text zone:

| Family | Title (words) | Subtitle (words) | Body (words) | Bullet item (words) | Max items |
|---|---|---|---|---|---|
| HERO | 6 | 12 | 0 | 0 | 0 |
| SECTION_DIVIDER | 4 | 8 | 0 | 0 | 0 |
| KEY_FACT | 6 | 0 | 25 | 10 | 3 |
| CARD_GRID | 6 | 0 | 0 | 15 | 4 |
| COMPARISON | 6 | 0 | 0 | 12 | 6 |
| TIMELINE | 6 | 0 | 0 | 10 | 5 |
| CLOSING | 4 | 8 | 15 | 0 | 0 |

### 3. Create visual role definitions

**File:** `pptx-service/app/domain/visual_roles.py`

Define `VisualRole` enum:
- `NONE` — no visual element
- `DECORATIVE_ICON` — small accent icon, low detail
- `HERO_IMAGE` — full-width or half-width hero visual
- `PHOTO` — realistic photograph
- `CHART` — data visualization (matplotlib)
- `COMPARISON_VISUAL` — paired images for comparison

### 4. Build content compressor

**File:** `pptx-service/app/compression/content_compressor.py`

Implement `ContentCompressor` class:
- Input: `SlideSpec` + target `LayoutFamily`
- Output: `CompressedSlideSpec`
- Uses Gemini to semantically compress text (not truncate)
- Runs two passes if first pass exceeds budget
- Extracts dominant assertion and preserves it
- Limits supporting details to `max_items` for the layout family
- Detects auto-split candidates (content exceeds 2x budget after compression)

### 5. Create compression prompt

**File:** `pptx-service/app/compression/prompts.py`

LLM prompt for the compressor:
- Specify exact word budget per zone
- Instruct to preserve the core message
- Instruct to eliminate filler words, redundant qualifiers, and generic phrases
- Instruct to convert sentences to concise noun phrases where appropriate
- Output format: JSON matching `CompressedSlideSpec` schema

### 6. Build hard quality gate

**File:** `pptx-service/app/quality/quality_gate.py`

Implement `QualityGate` class:
- Input: `CompressedSlideSpec` + `LayoutFamily`
- Scoring dimensions: word budget compliance, item count compliance, title length, assertion presence
- Score 0-100
- Hard block: score < 70 raises `QualityBlockError` with failure reasons
- Returns `QualityResult(score, passed, failures)`

### 7. Build replan engine (basic)

**File:** `pptx-service/app/quality/replan_engine.py`

Implement `ReplanEngine` class (basic version for Phase 1):
- Input: `CompressedSlideSpec` + `QualityResult`
- Strategy 1: Re-compress with 70% budget
- Strategy 2: Flag for manual review
- Max 2 iterations
- Returns: updated `CompressedSlideSpec` or `ReplanFailure`

### 8. Wire into V2 orchestrator

**File:** `pptx-service/app/pipeline/orchestrator.py` (modify existing)

Insert content compression as Stage 3.5:
- After Stage 3 (Slide Plan) and before Stage 4 (Validate)
- Map each planned slide's type to the nearest `LayoutFamily`
- Run `ContentCompressor` on each slide
- Run `QualityGate` on compressed output
- If blocked, run `ReplanEngine`
- Pass `CompressedSlideSpec` to Stage 5 instead of raw plan

### 9. Harden preflight gate

**File:** `pptx-service/app/validators/preflight.py` (modify existing)

Change behavior:
- Score < 70: raise exception instead of logging warning
- Add structured failure reasons to exception
- Integrate with replan engine trigger

---

## Acceptance Criteria

- [ ] All new domain models (`PresentationRequest`, `PresentationPlan`, `SlideSpec`, `CompressedSlideSpec`, `PlannedSlideSpec`, `RenderMode`, `LayoutFamily`, `VisualRole`) are defined as Pydantic models with full type annotations and validation.
- [ ] Content compressor reduces text by 30-50% on average across a test set of 20 sample slides.
- [ ] Hard quality gate blocks slides with score < 70 and provides actionable failure reasons.
- [ ] Replan engine resolves at least 80% of blocked slides within 2 iterations.
- [ ] Existing V2 API (`POST /api/v1/generate-v2`) continues to work with identical request/response format.
- [ ] New modules have pytest test coverage for core logic.
- [ ] No regression in V2 generation time beyond +2 seconds per slide (compression overhead).

---

## Files Created

| File | Purpose |
|---|---|
| `pptx-service/app/domain/models.py` | Core domain models |
| `pptx-service/app/domain/layout_families.py` | Layout family definitions + budgets |
| `pptx-service/app/domain/visual_roles.py` | Visual role enum |
| `pptx-service/app/compression/content_compressor.py` | Content compression service |
| `pptx-service/app/compression/prompts.py` | Compression LLM prompt |
| `pptx-service/app/quality/quality_gate.py` | Hard quality gate |
| `pptx-service/app/quality/replan_engine.py` | Basic replan engine |

## Files Modified

| File | Change |
|---|---|
| `pptx-service/app/pipeline/orchestrator.py` | Add Stage 3.5 (compression) |
| `pptx-service/app/validators/preflight.py` | Change warning to hard block |
