# Phase 3 — Template Mode with Deterministic Rendering

**Duration:** Week 5-6
**Goal:** Create a reliable corporate template filling pipeline that uses deterministic placeholder mapping instead of AI at render time.

---

## Context

The current template mode shares the orchestrator with design mode and has inconsistent quality gates (see [v2-pipeline-issues.md](v2-pipeline-issues.md), Issue 7). Phase 3 builds a dedicated template pipeline where templates are analyzed once at upload time, and filling is purely mechanical — no LLM calls during rendering.

---

## Tasks

### 1. Extract template analysis into dedicated module

**File:** `pptx-service/app/templates/template_analyzer.py`

Move and enhance template analysis logic:
- Extract from current `pptx-service/app/services/template_service.py`
- Analyze every slide layout in the template
- For each layout, catalog all placeholders: name, type (title, body, picture, chart, table), position (x, y, width, height in cm), font properties, max character estimate
- Store analysis results as a `TemplateDescriptor`
- Run analysis once at upload time, cache results alongside the template file

### 2. Create TemplateDescriptor model

**File:** `pptx-service/app/templates/template_descriptor.py`

Define Pydantic models:

```
TemplateDescriptor
  template_id: str
  template_hash: str              # SHA-256 of the .pptx file
  analyzed_at: datetime
  layouts: list[TemplateLayout]

TemplateLayout
  layout_index: int
  layout_name: str
  layout_family: LayoutFamily     # Mapped from Phase 1
  placeholders: list[PlaceholderSpec]

PlaceholderSpec
  placeholder_id: int
  name: str
  type: PlaceholderType           # TITLE, BODY, PICTURE, CHART, TABLE, OTHER
  position: Box                   # x, y, width, height in cm
  max_chars: int                  # Estimated from font size + box dimensions
  font_size_pt: float | None
  font_name: str | None
  is_required: bool
```

### 3. Integrate pptx-automizer

**File:** `pptx-service/app/templates/template_filler.py`

Integrate the `pptx-automizer` library for template manipulation:
- Use pptx-automizer to read template structure (validate against `TemplateDescriptor`)
- Use pptx-automizer to write content into placeholders
- Preserve all template formatting (fonts, colors, animations, transitions)
- Handle master slide and layout inheritance correctly

If pptx-automizer is not suitable for the Python ecosystem, fall back to enhanced python-pptx usage with explicit placeholder targeting (no layout inference).

### 4. Create deterministic placeholder fill logic

**File:** `pptx-service/app/templates/placeholder_filler.py`

Implement deterministic mapping:
- Input: `CompressedSlideSpec` + `TemplateLayout`
- Map `CompressedSlideSpec.title` to the placeholder with `type=TITLE`
- Map `CompressedSlideSpec.body` to the placeholder with `type=BODY`
- Map `CompressedSlideSpec.visual` to the placeholder with `type=PICTURE`
- Map `CompressedSlideSpec.chart_data` to the placeholder with `type=CHART`
- No LLM calls — mapping is by placeholder type only
- Log warnings for unmapped fields (content that has no matching placeholder)

### 5. Create overflow handling

**File:** `pptx-service/app/templates/overflow_handler.py`

Implement overflow prevention:
- Check each text field against `PlaceholderSpec.max_chars`
- If text exceeds capacity by < 20%: truncate at last word boundary, add ellipsis
- If text exceeds capacity by >= 20%: flag for slide splitting
- Slide splitting: create a continuation slide using the same template layout
- Title on continuation slide: original title + " (continued)"
- Never allow text to overflow the placeholder box

### 6. Create template versioning

**File:** `pptx-service/app/templates/template_versioning.py`

Implement hash-based versioning:
- On template upload, compute SHA-256 hash of the .pptx file
- Compare against stored `TemplateDescriptor.template_hash`
- If hashes match: reuse cached descriptor
- If hashes differ: invalidate cache, re-run analysis, store new descriptor
- Store descriptors as `.descriptor.json` alongside the template file

### 7. Create template fit validation

**File:** `pptx-service/app/templates/fit_validator.py`

Implement pre-render validation:
- Input: `PresentationPlan` + `TemplateDescriptor`
- Check: does the template have enough layouts to cover all planned slide types?
- Check: can each slide's content volume fit within the target layout's placeholders?
- Check: are required placeholders (title, body) present in each selected layout?
- Return: `FitResult(valid, issues)` with specific mismatch details
- Run before rendering begins to fail fast

### 8. Wire into existing template upload flow

**Files to modify:**
- `backend/src/templates/templates.service.ts`
- `backend/src/templates/templates.controller.ts`
- `pptx-service/app/api/routes/` (add template analysis endpoint)

Integration steps:
- On template upload in the backend, forward the file to pptx-service for analysis
- pptx-service runs `TemplateAnalyzer`, stores `TemplateDescriptor`
- Backend stores the descriptor reference alongside the template metadata
- On V2 generation with template mode, load the descriptor instead of re-analyzing

---

## Acceptance Criteria

- [ ] Templates are analyzed once at upload time; subsequent generations reuse cached descriptors.
- [ ] Placeholder mapping is fully deterministic — no LLM calls during template rendering.
- [ ] Text never overflows placeholder boundaries (truncation + splitting handles all cases).
- [ ] Template branding (fonts, colors, logos, master slide) is preserved exactly in output.
- [ ] Re-uploading a modified template triggers re-analysis automatically (hash comparison).
- [ ] Fit validation catches template/content mismatches before rendering starts.
- [ ] Template mode produces valid PPTX that opens correctly in PowerPoint, Google Slides, and LibreOffice.
- [ ] All new modules have pytest test coverage.

---

## Files Created

| File | Purpose |
|---|---|
| `pptx-service/app/templates/template_analyzer.py` | Template analysis at upload time |
| `pptx-service/app/templates/template_descriptor.py` | TemplateDescriptor Pydantic models |
| `pptx-service/app/templates/template_filler.py` | pptx-automizer integration |
| `pptx-service/app/templates/placeholder_filler.py` | Deterministic placeholder mapping |
| `pptx-service/app/templates/overflow_handler.py` | Overflow prevention + slide splitting |
| `pptx-service/app/templates/template_versioning.py` | Hash-based versioning |
| `pptx-service/app/templates/fit_validator.py` | Pre-render fit validation |

## Files Modified

| File | Change |
|---|---|
| `backend/src/templates/templates.service.ts` | Trigger analysis on upload |
| `backend/src/templates/templates.controller.ts` | Forward template for analysis |
| `pptx-service/app/api/routes/` | Add template analysis endpoint |
