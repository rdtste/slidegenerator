# V3 Pipeline — Full Backlog

This document organizes the V3 pipeline refactoring as epics with user stories. Each epic represents a major capability area. Stories are written from the perspective of the system or developer.

---

## Epic 1: Domain Model Foundation

**Goal:** Establish the shared vocabulary and data structures that all V3 components will use.

### Stories

**1.1 — PresentationRequest model**
As a developer, I need a `PresentationRequest` Pydantic model that captures the user's intent (topic, audience, tone, slide count preference, template reference) so that all downstream stages operate on a well-typed input.

**1.2 — PresentationPlan model**
As a developer, I need a `PresentationPlan` model that holds the ordered list of planned slides with their intent, layout family, and visual role assignments, so that the plan can be validated before content generation.

**1.3 — SlideSpec model**
As a developer, I need a `SlideSpec` model representing a single slide's raw content (title, body, bullets, visual descriptions, chart data) as produced by the LLM, before compression.

**1.4 — CompressedSlideSpec model**
As a developer, I need a `CompressedSlideSpec` model that holds content after compression, with word counts verified against budgets, so that downstream rendering can trust the content fits.

**1.5 — PlannedSlideSpec model**
As a developer, I need a `PlannedSlideSpec` model that combines compressed content with resolved layout coordinates and visual assets, ready for rendering.

**1.6 — RenderMode enum**
As a developer, I need a `RenderMode` enum (`DESIGN`, `TEMPLATE`) so that the orchestrator can cleanly branch between rendering paths without conditional string checks.

**1.7 — VisualRole enum**
As a developer, I need a `VisualRole` enum (`NONE`, `DECORATIVE_ICON`, `HERO_IMAGE`, `PHOTO`, `CHART`, `COMPARISON_VISUAL`) so that the image service knows the purpose of each image and can adjust prompt style, aspect ratio, and quality accordingly.

**1.8 — LayoutFamily enum**
As a developer, I need a `LayoutFamily` enum with 7 families (`HERO`, `SECTION_DIVIDER`, `TIMELINE`, `CARD_GRID`, `COMPARISON`, `KEY_FACT`, `CLOSING`) to replace the current 14 slide types with fewer, higher-quality layout options.

**1.9 — Hard budgets per LayoutFamily**
As a developer, I need a budget table that defines maximum word counts per text zone (title, subtitle, body, bullet_item, card_text) for each `LayoutFamily`, so that the content compressor has explicit targets.

---

## Epic 2: Content Compression Module

**Goal:** Ensure LLM-generated content fits within layout budgets through semantic compression.

### Stories

**2.1 — Content compressor service**
As a developer, I need a `content_compressor` service (`pptx-service/app/compression/content_compressor.py`) that takes a `SlideSpec` and its target `LayoutFamily` budgets and returns a `CompressedSlideSpec`.

**2.2 — LLM-based semantic compression**
As a developer, I need the compressor to use Gemini to semantically compress text (preserving meaning, removing filler) rather than naive truncation, so that compressed content remains coherent.

**2.3 — Word budget enforcement**
As a developer, I need the compressor to hard-enforce word budgets: if the LLM output still exceeds the budget after one compression pass, a second pass with stricter instructions runs automatically.

**2.4 — Auto-split detection**
As a developer, I need the compressor to detect when a single slide's content cannot fit within budgets even after maximum compression, and flag it for splitting into two slides.

**2.5 — Dominant assertion extraction**
As a developer, I need the compressor to identify the single most important assertion per slide and ensure it survives compression intact, so that every slide has a clear takeaway.

**2.6 — Supporting detail limiting**
As a developer, I need the compressor to limit supporting details (bullets, sub-points) to a maximum count per layout family (e.g., 3 bullets for KEY_FACT, 4 cards for CARD_GRID).

---

## Epic 3: Slide Intent & Layout Planning

**Goal:** Match each slide's content intent to the best layout family and allocate text budgets per zone.

### Stories

**3.1 — Slide intent planner**
As a developer, I need a `slide_intent_planner` service that analyzes each slide's content and assigns an intent label (e.g., "introduce topic", "compare options", "show timeline", "present data"), so that layout selection is intent-driven.

**3.2 — Layout candidate selector**
As a developer, I need a `layout_candidate_selector` service that maps slide intents to compatible `LayoutFamily` options (ranked by fit), so that the pipeline can choose or fall back to alternatives.

**3.3 — Layout family matching**
As a developer, I need the layout selector to score each candidate based on content characteristics (text volume, number of items, presence of visuals, data density) and select the best fit.

**3.4 — Text budget allocation per zone**
As a developer, I need the planner to allocate specific word budgets to each text zone (title, body, bullets) based on the selected layout family and the slide's content distribution.

**3.5 — Visual role assignment**
As a developer, I need the planner to assign a `VisualRole` to each slide based on its intent and content, so that the image service receives clear direction on what kind of visual to generate.

---

## Epic 4: Design Mode Preview

**Goal:** Create a TypeScript-based rendering service that produces HTML previews and PPTX exports for design mode.

### Stories

**4.1 — TypeScript render service setup**
As a developer, I need a new `rendering-service/` Node.js project (TypeScript, React, Tailwind CSS) that can receive slide specs via HTTP and return rendered output.

**4.2 — Layout family React components**
As a developer, I need 7 React components (one per layout family: HERO, SECTION_DIVIDER, TIMELINE, CARD_GRID, COMPARISON, KEY_FACT, CLOSING) that render slides as styled HTML.

**4.3 — Server-side slide preview renderer**
As a developer, I need a server-side React renderer that produces static HTML for each slide, suitable for screenshot capture.

**4.4 — Puppeteer screenshot pipeline**
As a developer, I need a Puppeteer-based pipeline that renders each slide's HTML at 1920x1080, captures a PNG screenshot, and returns it for quality review.

**4.5 — PptxGenJS export module**
As a developer, I need a PptxGenJS-based export module that translates the same React component data into a valid PPTX file, ensuring visual parity with the HTML preview.

**4.6 — Visual review engine integration**
As a developer, I need the screenshot pipeline to feed into the visual review engine for automated quality scoring before export.

**4.7 — Python-to-TypeScript HTTP bridge**
As a developer, I need the Python orchestrator to call the TypeScript render service via HTTP (`/api/v1/render-preview` and `/api/v1/render-export`), passing `PlannedSlideSpec` payloads.

**4.8 — Preview endpoint**
As a developer, I need a `POST /api/v1/render-preview` endpoint on the rendering service that accepts a slide spec and returns an HTML preview with screenshot.

**4.9 — Export endpoint**
As a developer, I need a `POST /api/v1/render-export` endpoint on the rendering service that accepts a full deck spec and returns a PPTX file.

---

## Epic 5: Visual Quality Gate

**Goal:** Implement a scoring system that blocks low-quality slides before they reach export.

### Stories

**5.1 — Visual review engine**
As a developer, I need a `visual_review_engine` service that scores rendered slides across multiple quality dimensions.

**5.2 — Rule-based scoring dimensions**
As a developer, I need scoring rules for: text density (chars per cm^2), visual hierarchy (title prominence vs body), whitespace balance (margin utilization), element alignment, and font size consistency.

**5.3 — Optional Vision AI scoring**
As a developer, I need an optional Gemini Vision scoring pass that evaluates the screenshot holistically for professional appearance, usable as a secondary signal.

**5.4 — Hard block implementation**
As a developer, I need the quality gate to hard-block any slide scoring below the threshold (default: 70/100), preventing it from appearing in the export without remediation.

**5.5 — Replan trigger mechanism**
As a developer, I need blocked slides to automatically trigger the replan engine with the specific failure reasons, so that remediation is automatic rather than manual.

---

## Epic 6: Replan Engine

**Goal:** Automatically remediate slides that fail the quality gate.

### Stories

**6.1 — Replan engine service**
As a developer, I need a `replan_engine` service that receives a blocked slide with its failure reasons and applies remediation strategies.

**6.2 — Content reduction strategy**
As a developer, I need a replan strategy that re-runs content compression with tighter budgets (e.g., 70% of original budget) when the failure reason is text overflow or density.

**6.3 — Layout variant switching**
As a developer, I need a replan strategy that switches to an alternative layout family from the candidate list when the current layout cannot accommodate the content.

**6.4 — Slide splitting**
As a developer, I need a replan strategy that splits a single overfilled slide into two slides when compression and layout switching are insufficient.

**6.5 — Max iteration guard**
As a developer, I need the replan engine to attempt a maximum of 2 iterations per slide, after which the best-scoring attempt is used with a quality warning attached to the export metadata.

---

## Epic 7: Template Mode

**Goal:** Create a deterministic pipeline for filling corporate templates without AI at render time.

### Stories

**7.1 — Template analysis at upload time**
As a developer, I need template analysis to run once when a template is uploaded, extracting all placeholder positions, sizes, font styles, and color schemes into a cached descriptor.

**7.2 — TemplateDescriptor with explicit mappings**
As a developer, I need a `TemplateDescriptor` Pydantic model that maps each template slide layout to its placeholders (name, type, position, max characters), so that filling is deterministic.

**7.3 — pptx-automizer integration**
As a developer, I need to integrate the `pptx-automizer` library for reading and writing template placeholders, replacing direct python-pptx manipulation for template mode.

**7.4 — Deterministic placeholder filling**
As a developer, I need a fill service that maps `CompressedSlideSpec` fields to template placeholders by name/type, with no LLM calls at render time.

**7.5 — Overflow handling**
As a developer, I need overflow handling that truncates text at word boundaries when content exceeds placeholder capacity, and triggers slide splitting when truncation would lose critical content.

**7.6 — Template versioning**
As a developer, I need hash-based template versioning so that re-uploading a modified template invalidates the cached descriptor and triggers re-analysis.

**7.7 — Template fit validation**
As a developer, I need a validation step that checks whether the planned slide count and content volumes can fit the available template layouts before rendering begins.

**7.8 — Integration with upload flow**
As a developer, I need to wire template analysis into the existing template upload flow (`backend/src/templates/`), so that descriptors are generated automatically on upload.

---

## Epic 8: Deck-Level Review

**Goal:** Ensure the complete deck is coherent, not just individual slides.

### Stories

**8.1 — Style consistency check**
As a developer, I need a deck-level check that verifies all slides use consistent font sizes, color palettes, and spacing rules.

**8.2 — Slide rhythm analysis**
As a developer, I need a check that evaluates slide rhythm — ensuring the deck alternates between content-heavy and visual-light slides, avoiding sequences of identical layout families.

**8.3 — Visual consistency**
As a developer, I need a check that verifies generated images across the deck share a consistent style (color temperature, illustration style, level of detail).

**8.4 — Title quality check**
As a developer, I need a check that verifies slide titles are concise (under 8 words), unique across the deck, and follow a consistent grammatical pattern.

**8.5 — Redundancy detection**
As a developer, I need a check that detects slides with substantially overlapping content and flags them for merging or differentiation.
