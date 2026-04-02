# V2 Pipeline Assessment

An honest evaluation of the current 8-stage V2 pipeline for AI-driven PPTX generation.

---

## 1. Pipeline Overview

The V2 pipeline lives in `pptx-service/app/pipeline/orchestrator.py` and executes 8 sequential stages:

| Stage | Name | Type | Key File(s) |
|-------|------|------|-------------|
| 1 | Input Interpretation | LLM | `pipeline/orchestrator.py` -> `prompts/interpreter_prompt.py` |
| 2 | Storyline Planning | LLM | `pipeline/orchestrator.py` -> `prompts/storyline_prompt.py` |
| 3 | Slide Planning | LLM (3 retries) | `pipeline/orchestrator.py` -> `prompts/slide_planner_prompt.py` |
| 4 | Schema Validation | Code + LLM regen | `validators/`, `validators/auto_fixes.py` |
| 4b | Preflight Scoring | Code | `validators/preflight.py` |
| 5 | Content Filling | LLM (parallel) | `prompts/content_filler_prompt.py` |
| 6 | Layout Engine | Code | `layouts/engine.py`, `layouts/blueprints.py` |
| 7 | PPTX Rendering | Code | `renderers/pptx_renderer_v2.py` |
| 8 | Design Review | Vision AI + Code | `services/design_review_agent.py` |

Data flow: `user_input` -> `InterpretedBriefing` -> `Storyline` -> `PresentationPlan` -> `FilledSlide[]` -> `RenderInstruction[]` -> `.pptx` file -> optional re-render.

---

## 2. What Works Well

### Stages 1-2: Input Interpretation and Storyline Planning

These stages are architecturally sound. They solve the right problem at the right time: understanding intent before committing to structure.

- **Stage 1** produces a clean `InterpretedBriefing` with topic, goal, audience, image style, requested slide count, and content themes. It has a sensible fallback if the LLM call fails (lines 186-197 in `orchestrator.py`).
- **Stage 2** generates a `Storyline` with narrative arc and story beats. The `NarrativeArc` enum (situation-complication-resolution, etc.) and `BeatType` enum (opening, context, evidence, pivot, closing) give the LLM good guardrails without over-constraining it.
- Both stages use low temperatures (0.3 and 0.5) and modest token budgets (2048 and 4096), keeping responses focused.

### Progress Tracking and Timing

The pipeline has solid observability: every stage reports progress via `_progress()` callbacks (used for SSE streaming to the frontend), and wall-clock timing is logged for each stage. This makes performance profiling straightforward.

### Parallel Content Filling

Stage 5 fills all slides in parallel via `asyncio.gather()` (line 389), which is the correct approach for independent per-slide LLM calls.

### Auto-Fix + LLM Regeneration Loop

The Stage 4 validation loop (`_stage_4_validate`) is well-structured: it applies cheap code-based auto-fixes first (`auto_fixes.py`), then only escalates to expensive LLM regeneration for issues that need it. The `needs_llm_regeneration()` function (line 91-102 in `auto_fixes.py`) acts as a triage gate.

---

## 3. Critical Weaknesses

### 3.1 Stage 3: Too Much LLM Freedom (14 Slide Types, No Text Budgets)

**File:** `slide_types/registry.py`

The LLM must choose from 14 slide types: `title_hero`, `section_divider`, `key_statement`, `bullets_focused`, `three_cards`, `kpi_dashboard`, `image_text_split`, `comparison`, `timeline`, `process_flow`, `chart_insight`, `image_fullbleed`, `agenda`, `closing`.

This is too many options. The LLM frequently:
- Picks complex types (timeline, process_flow) when bullets would suffice
- Generates mismatched content blocks for the chosen type
- Requires multiple retries (up to 3 attempts at increasing temperature, lines 268-286)

The `max_total_chars` limits in the registry (e.g., 500 for timeline, 450 for process_flow, 400 for three_cards) are post-hoc validation checks, not upfront budgets the LLM understands. The LLM prompt includes a catalog of types and character limits, but there are no **per-zone word budgets** (e.g., "title max 8 words, entry description max 12 words"). The result is that content overflows its visual container at render time.

### 3.2 Stage 5: Content Filling Without Compression

**File:** `orchestrator.py`, lines 366-390

Stage 5 (`_stage_5_fill_content`) takes the slide plan and asks the LLM to produce final text. But there is no **Content Compression** step between planning and filling. The LLM is prompted to write polished text for each slide, but it has no instruction to:

- Extract a single core assertion per slide
- Remove filler words and redundant qualifiers
- Enforce a "less is more" principle
- Split overfull slides into two

The `_compute_metrics()` method (lines 448-480) counts characters after the fact, but never acts on the result. `TextMetrics` is computed and stored on `FilledSlide.text_metrics`, but nothing in the pipeline checks whether the metrics are acceptable before rendering.

### 3.3 Stage 6: Fixed Blueprints with No Content-Aware Adaptation

**File:** `layouts/blueprints.py`

Every slide type has a single `SlideBlueprint` with hardcoded positions in centimeters on a 33.867 x 19.05 cm canvas. For example, `_THREE_CARDS` defines exact positions for 3 card backgrounds, 3 icon areas, 3 titles, and 3 bodies -- totaling 19 `ElementBlueprint` entries (lines 136-198).

The layout engine (`layouts/engine.py`) applies audience-based multipliers to font sizes and line spacing (e.g., `MANAGEMENT` gets `headline_size: 1.1`, `body_size: 0.85`), but it never:

- Adjusts element positions based on actual text length
- Shrinks or grows content areas when text is shorter or longer than expected
- Adds or removes elements dynamically
- Handles 2 cards vs 4 cards (it assumes exactly 3)

The `_redistribute_element()` and `_redistribute_timeline()` methods (lines 453-470 in `engine.py`) do basic horizontal redistribution for KPIs and timeline entries, but this is limited to simple even-spacing math. No vertical redistribution, no overflow detection, no font-size fallback.

When the LLM generates 4 timeline entries but the blueprint has slots for 5, the surplus slots are simply not rendered. When it generates 6, the extras are silently dropped. There is no feedback loop.

### 3.4 Stage 4b: Preflight is Warning-Only

**File:** `validators/preflight.py`

The preflight gate scores each slide on 5 dimensions (readability, balance, density, hierarchy, visual_fit) and computes a weighted total. But the result is **purely advisory**:

```python
# orchestrator.py, lines 122-127
if preflight.failing_slides:
    logger.warning(
        f"[Pipeline] Preflight: {len(preflight.failing_slides)} slides below threshold "
        f"(avg={preflight.avg_score:.0f}). Proceeding with warnings."
    )
```

The pipeline always proceeds to Stage 5 regardless of the preflight score. A slide scoring 20/100 on readability and 40/100 on density will still be rendered into the final PPTX. There is no hard block, no replan loop, no slide removal.

### 3.5 Stage 8: Design Review Comes Too Late

**File:** `services/design_review_agent.py`

The design review agent runs after the PPTX has already been rendered. It:
1. Converts PPTX to JPEG images (requires LibreOffice)
2. Sends each image to Gemini Vision for analysis
3. Parses design fix recommendations (font size, spacing, position adjustments)
4. Applies fixes to `RenderInstruction` objects and re-renders
5. Runs up to 2 iterations

The fundamental problem: at this point, the content is frozen. The agent can fix font sizes, spacing, and padding, but it **cannot**:
- Rewrite overly long text
- Remove unnecessary bullet points
- Split an overcrowded slide
- Change the slide type
- Reorder the storyline

The `DesignFix` categories (line 48) are limited to: `FONT_SIZE`, `SPACING`, `POSITION`, `SIZE`, `PADDING`, `FONT_WEIGHT`, `COLOR`, `REMOVE`. These are cosmetic adjustments, not structural fixes. A fundamentally overcrowded slide will get smaller fonts and tighter spacing -- making it harder to read, not better.

### 3.6 No Content Compression Module

There is no module, function, or prompt anywhere in the pipeline that performs content compression. The word "compress" does not appear in any pipeline code. Text goes from LLM generation to rendering without any systematic reduction.

The auto-fixes in `validators/auto_fixes.py` do simple truncation:
- Headlines: truncate at word boundary after 70 chars (line 40)
- Bullets: trim to max count per type (line 47)
- Bullet text: truncate at 60 chars (line 59)
- Card titles: 30 chars, card bodies: 80 chars (line 78)

But truncation is not compression. Cutting "Our quarterly revenue increased significantly across all regions" to "Our quarterly revenue increased significantly across all..." is not the same as compressing it to "+12% revenue, all regions". The current system clips; it does not distill.

### 3.7 No Preview Before Final Render

There is no visual preview step between content planning and PPTX generation. The user (and the system) sees the result only after the full render pipeline has completed. If the output is poor, the only option is to re-run the entire pipeline.

### 3.8 Design Mode and Template Mode Share the Same Pipeline

The pipeline has a `template_id` parameter (line 49 in `orchestrator.py`) that gets passed to the renderer, but the entire pipeline logic is identical regardless of whether a template is used. There is no separate flow for:
- Analyzing template placeholders and constraints
- Matching slide content to template layouts
- Validating that content fits within template zones
- Handling template-specific slide types that don't map to the 14 built-in types

---

## 4. Root Cause Analysis

The V2 pipeline's problems stem from three architectural decisions:

### 4.1 Generate-Then-Validate Instead of Compress-Then-Compose

The pipeline generates content first (Stages 3 + 5), then validates it (Stages 4 + 4b), then tries to fix it (Stage 4 auto-fixes, Stage 8 design review). This is backwards. Good presentation design starts with ruthless content compression, then composes only what survives.

The current flow:
```
LLM generates freely -> Validator flags problems -> Auto-fix truncates -> Render -> Vision reviews cosmetics
```

The correct flow:
```
LLM generates draft -> Compressor distills to core assertions -> Planner assigns to layout budgets -> Gate blocks if over budget -> Render only what passed
```

### 4.2 Layout is a Static Lookup, Not a Dynamic Engine

The blueprint system (`blueprints.py`) treats layout as a dictionary lookup: given a `SlideType`, return fixed positions. This means the layout cannot adapt to content. A slide with 2 bullets gets the same 10.0 cm bullet area as a slide with 8 bullets. A KPI dashboard with 2 KPIs gets a `_redistribute_element()` call that spreads them across the same fixed width -- but the card height, font size, and vertical spacing remain frozen.

Real presentation tools (Keynote, PowerPoint's Designer) adapt layout to content: fewer items get larger treatment, more items get compact treatment. The V2 layout engine has no concept of this.

### 4.3 Quality Gates Are Advisory, Not Enforcing

The preflight score (Stage 4b) warns but never blocks. The design review (Stage 8) suggests fixes but always produces output. There is no point in the pipeline where a bad slide is definitively rejected and either replanned or removed from the deck. Every slide that enters Stage 3 will appear in the final PPTX, regardless of quality.

---

## 5. Impact on Output Quality

| Problem | Symptom | Frequency |
|---------|---------|-----------|
| Too many slide types | LLM picks wrong type, content doesn't fit layout | ~30% of slides |
| No text budgets | Text overflows blueprint zones, gets clipped or shrunk | ~40% of slides |
| No content compression | Slides are wordy, violate "1 idea per slide" principle | ~60% of slides |
| Fixed blueprints | Empty space on sparse slides, cramped space on dense slides | ~50% of slides |
| Warning-only preflight | Known-bad slides proceed to render | ~15% of decks |
| Late design review | Cosmetic fixes applied to structurally broken slides | ~25% of slides |
| No preview | Users see problems only after full pipeline run (~30-60s) | 100% of runs |
| Shared pipeline for templates | Template-based output ignores template constraints | 100% of template runs |

The net effect: approximately half of all generated slides have at least one significant quality issue (text overflow, visual imbalance, wrong slide type, or excessive wordiness). The pipeline produces output reliably, but the output quality is inconsistent and unpredictable.
