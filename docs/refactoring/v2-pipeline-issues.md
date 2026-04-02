# V2 Pipeline Issues — Root Cause Analysis

This document catalogs the structural issues in the current V2 pipeline that motivate the V3 refactoring effort. Each issue references the specific files and code paths involved.

---

## 1. Content Overfilling

**Stage:** 5 (Fill Content)
**Files:**
- `pptx-service/app/pipeline/orchestrator.py` — method `_stage_5_fill_content`
- `pptx-service/app/prompts/content_filler_prompt.py`

**Problem:**
The LLM fills slide content without any word or character budgets. The content filler prompt (`content_filler_prompt.py`) instructs the model to generate text for each slide, but does not enforce reduction targets or maximum lengths per text zone.

**Symptoms:**
- Slides routinely contain 200-400 characters of body text when 80-120 characters would be optimal for visual balance.
- Bullet points are full sentences instead of concise phrases.
- Titles are verbose and wrap to multiple lines.

**Root cause:**
There is no compression step between content generation (Stage 5) and layout application (Stage 6). The pipeline assumes the LLM will self-regulate text volume, which it consistently fails to do.

**Impact:** Overfilled slides lead to text overflow, tiny font sizes, and cramped layouts in the final PPTX.

---

## 2. Static Blueprints

**Stage:** 6 (Layout)
**Files:**
- `pptx-service/app/layouts/blueprints.py`

**Problem:**
All 14 layout types are defined as static blueprints with fixed centimeter coordinates for every element (title, body, image, chart, etc.). These coordinates do not adapt based on actual content volume.

**Symptoms:**
- A slide with 3 bullet points and a slide with 8 bullet points get identical element placement.
- Image placeholders are sized identically whether the slide has a paragraph of text or a single line.
- No preview step exists to verify that content fits before committing to a layout.

**Root cause:**
Blueprints are pure geometry — they encode where elements go, not how elements should respond to varying content. There is no feedback loop between content volume and layout dimensions.

**Impact:** Slides with sparse content look empty; slides with dense content look cramped. Neither case produces professional results.

---

## 3. Weak Quality Gate

**Stage:** 4b (Preflight Validation)
**Files:**
- `pptx-service/app/validators/preflight.py`

**Problem:**
The preflight validator calculates a composite score but treats failure as a warning, not a block. The pass condition (`return self.total >= _comp.preflight_pass_score`) uses a threshold (typically 70) below which the slide is flagged but still continues through the pipeline.

**Symptoms:**
- Slides with score 40-69 produce warnings in logs but render anyway.
- No mechanism exists to trigger replanning when a slide fails validation.
- Bad slide plans are never rejected — they always proceed to content fill and rendering.

**Root cause:**
The preflight was designed as an informational check, not a gate. There is no replan engine to handle rejected slides, so blocking was never implemented.

**Impact:** Known-bad slides consume rendering resources and produce low-quality output that degrades the entire deck.

---

## 4. Late Vision Review

**Stage:** 8 (Design Review)
**Files:**
- `pptx-service/app/services/design_review_agent.py`

**Problem:**
The vision-based design review runs only after the PPTX file has been fully rendered. At this point, the review can only make superficial fixes (font size adjustments, spacing tweaks) — it cannot change the fundamental composition of a slide.

**Symptoms:**
- Reviews correctly identify overfilled slides but can only suggest font reduction, not content reduction.
- Layout issues (wrong layout type for content) cannot be corrected post-render.
- Maximum 2 review iterations are allowed, which is often insufficient for slides with multiple issues.
- Content removal or layout switching would require re-running the entire pipeline, which the review agent cannot trigger.

**Root cause:**
The review was added as a post-hoc safety net rather than being integrated into the planning loop. By Stage 8, all upstream decisions (content volume, layout choice, visual placement) are already baked into the file.

**Impact:** The review catches problems it cannot fix, resulting in marginal improvements at best.

---

## 5. Too Many Slide Types

**Files:**
- `pptx-service/app/slide_types/` (14 type definitions)

**Problem:**
The pipeline offers 14 distinct slide types: `title_hero`, `section_divider`, `key_statement`, `bullets_focused`, `three_cards`, `kpi_dashboard`, `image_text_split`, `comparison`, `timeline`, `process_flow`, `chart_insight`, `image_fullbleed`, `agenda`, `closing`.

**Symptoms:**
- The LLM frequently selects suboptimal types (e.g., `image_fullbleed` when content is text-heavy).
- Some types (`image_fullbleed`, `agenda`) rarely produce good results due to strict visual requirements.
- The LLM must reason over 14 options in the slide plan stage, increasing the chance of poor selections.

**Root cause:**
Slide types were added incrementally without evaluating whether each type consistently produces high-quality output. The type catalog grew without quality curation.

**Impact:** More choice does not mean better output. Reducing to fewer, well-tested layout families would improve consistency.

---

## 6. Uncurated Visuals

**Files:**
- `pptx-service/app/services/image_service.py`

**Problem:**
Image generation uses Vertex AI Imagen 3.0 with generic prompts that lack visual role context. The service generates images without understanding whether the image serves as a hero visual, a decorative icon, a comparison element, or a data illustration.

**Symptoms:**
- All images get the same generic prompt treatment regardless of their role on the slide.
- Descriptor texts (meant for the AI) sometimes leak into visible slide content.
- No consistency enforcement exists across images in a deck — each image is generated independently with no shared style direction.
- Image style varies wildly between slides in the same presentation.

**Root cause:**
There is no visual role system. The image service receives a text prompt and returns an image, with no context about how the image will be used or what other images exist in the deck.

**Impact:** Decks look visually incoherent, with mismatched image styles undermining professional appearance.

---

## 7. Mixed Rendering Modes

**Files:**
- `pptx-service/app/api/routes/generate_v2.py`

**Problem:**
The V2 endpoint handles both "design mode" (build slides from scratch using blueprints) and "template mode" (fill an existing corporate template). Both modes share the same orchestrator but diverge at rendering time with inconsistent quality gates.

**Symptoms:**
- Template mode has a separate code path but inherits design mode assumptions about layout flexibility.
- Quality validation logic differs between modes without clear documentation of why.
- Bugs fixed in one mode are not automatically applied to the other.
- No clear separation of concerns — the orchestrator mixes mode-specific logic with shared logic.

**Root cause:**
Template mode was added as an extension of design mode rather than being designed as a first-class rendering pipeline. The shared orchestrator became a catch-all with conditional branching instead of clean mode separation.

**Impact:** Both modes are harder to maintain and improve independently. Changes risk breaking the other mode.
