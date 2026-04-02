# V3 Target Pipeline Architecture

The V3 pipeline replaces V2's "generate -> validate -> fix" approach with "compress -> compose -> gate -> render". No slide reaches the final export without passing a hard quality gate.

---

## Design Principles

1. **Content compression before rendering.** Every slide must carry exactly one dominant assertion. Filler is removed before layout, not after.
2. **Hard quality gates.** If a slide fails the visual quality gate, it is replanned or removed. There is no "proceed with warnings" path.
3. **HTML-first design mode.** Design Mode renders to HTML/CSS for instant preview. PPTX export is a downstream conversion, not the primary design surface.
4. **Separate Template Mode.** Corporate template filling is a distinct pipeline branch with deterministic placeholder mapping, not a parameter toggle on the same pipeline.
5. **Fewer slide types, hard budgets.** 7 layout families instead of 14, each with strict word-count budgets per zone.

---

## Pipeline Stages

### Stage 1 -- Input Understanding

**Replaces:** V2 Stage 1 (Input Interpretation)

**Responsibility:** Normalize all input sources into a single `PresentationRequest` object. Parse prompt text, extract document content, identify audience, purpose, branding preferences, and determine render mode.

**Input:**
```
- user_prompt: str
- documents: list[DocumentAttachment]   # uploaded PDFs, DOCX, etc.
- audience: Audience
- purpose: PresentationPurpose          # inform, persuade, workshop, report
- branding: BrandingConfig              # colors, fonts, logo, template_id
- render_mode: RenderMode               # DESIGN or TEMPLATE
```

**Output:** `PresentationRequest`
```
- topic: str
- goal: str
- audience: Audience
- purpose: PresentationPurpose
- render_mode: RenderMode
- branding: BrandingConfig
- source_content: str                   # merged and cleaned document text
- requested_slide_count: int
- language: str
- constraints: list[str]                # user-specified constraints
```

**Hard rules:**
- `render_mode` must be explicitly set; no implicit detection.
- If `render_mode == TEMPLATE`, a valid `template_id` must be present in `branding`.
- Document text is cleaned and deduplicated before being passed downstream.

---

### Stage 2 -- Presentation Strategy

**Replaces:** V2 Stage 2 (Storyline Planning) + parts of V2 Stage 3 (slide count, type distribution)

**Responsibility:** Generate the storyline, chapter structure, per-slide intents, and visual tonality. Decide how many slides to create and what each slide's narrative role is -- but do NOT select layout types yet.

**Input:** `PresentationRequest`

**Output:** `PresentationPlan`
```
- narrative_arc: NarrativeArc
- visual_tonality: VisualTonality       # minimal, editorial, data-heavy, photographic
- chapters: list[Chapter]
  - title: str
  - slides: list[SlideIntent]
    - position: int
    - narrative_role: NarrativeRole      # opening, context, evidence, pivot, insight, closing
    - core_assertion: str               # THE one thing this slide must communicate
    - supporting_points: list[str]      # max 3
    - data_hint: DataHint | None        # kpi, chart, comparison, timeline, process
    - visual_hint: VisualHint | None    # hero_image, icon_set, none
```

**Hard rules:**
- `core_assertion` is mandatory and must be a single sentence (max 20 words).
- `supporting_points` is capped at 3 items.
- Total slide count must not exceed `requested_slide_count * 1.2`.
- Each chapter must have at least 1 slide and at most 8 slides.

---

### Stage 3 -- Content Compression (NEW)

**Replaces:** Nothing in V2. This stage does not exist in the current pipeline.

**Responsibility:** Take each slide's `core_assertion` and `supporting_points` and compress them to fit within the word budgets of the target layout family. Remove filler words, merge redundant points, enforce one dominant assertion per slide. Split overfull slides if compression alone is insufficient.

**Input:** `PresentationPlan`

**Output:** `CompressedSlideSpec[]`
```
- position: int
- core_assertion: str                   # compressed, max 15 words
- compressed_points: list[CompressedPoint]
  - text: str                           # max word count depends on layout family
  - emphasis: Emphasis                  # primary, secondary, muted
- data_payload: DataPayload | None      # structured data for charts/KPIs
- compression_ratio: float              # original_words / compressed_words
- split_from: int | None                # if this slide was split from another
```

**Hard rules:**
- `core_assertion` must be <= 15 words after compression.
- Each `compressed_point.text` must be <= 15 words.
- If a slide cannot be compressed below budget, it MUST be split into 2 slides. The compressor adds a new `CompressedSlideSpec` with `split_from` set to the original position.
- `compression_ratio` must be >= 1.5 (i.e., at least 33% reduction from input). If the input is already concise, ratio can be 1.0.
- No bullet point may be a complete sentence. Sentence fragments only.

---

### Stage 4 -- Slide Intent and Layout Selection (NEW)

**Replaces:** V2 Stage 3 (slide type selection) + V2 Stage 6 (layout engine)

**Responsibility:** Assign each compressed slide to one of 7 layout families. Set the visual role, select a layout variant within the family, and assign per-zone text budgets.

**Input:** `CompressedSlideSpec[]`

**Output:** `PlannedSlideSpec[]`
```
- position: int
- layout_family: LayoutFamily           # hero, section_divider, timeline, card_grid, comparison, key_fact, closing
- layout_variant: str                   # e.g., "hero_image_right", "hero_text_only"
- visual_role: VisualRole               # dominant_image, supporting_image, icon_set, data_viz, none
- zones: list[ContentZone]
  - zone_id: str                        # "title", "subtitle", "card_0_title", "card_0_body", etc.
  - content: str                        # actual text for this zone
  - max_words: int                      # hard budget for this zone
  - actual_words: int                   # current word count
- data_payload: DataPayload | None
- budget_utilization: float             # sum(actual_words) / sum(max_words)
```

**Hard rules:**
- Every zone's `actual_words` must be <= `max_words`. No exceptions.
- `budget_utilization` should be between 0.5 and 1.0. Below 0.5 is underfilled (waste). Above 1.0 is impossible (hard block).
- Layout family selection is based on `data_hint` and `narrative_role`, not LLM free choice.

**Layout family selection logic:**

| `narrative_role` | `data_hint` | Layout Family |
|------------------|-------------|---------------|
| opening | any | hero |
| closing | any | closing |
| context (chapter start) | none | section_divider |
| evidence | kpi | key_fact |
| evidence | chart | key_fact (with data_viz) |
| evidence | comparison | comparison |
| evidence | timeline | timeline |
| evidence | process | timeline |
| insight | none | card_grid |
| any (default) | none | card_grid |

---

### Stage 5 -- Preview Composition (NEW)

**Replaces:** Nothing in V2. V2 has no preview step.

**Responsibility:**

- **Design Mode:** Render each `PlannedSlideSpec` as an HTML/CSS slide using React/Tailwind components. Produce a browser-viewable preview that matches the final PPTX output with high fidelity.
- **Template Mode:** Validate that each `PlannedSlideSpec` fits within the corporate template's placeholder zones. Report mismatches (content exceeds placeholder, missing placeholder, type mismatch).

**Input:** `PlannedSlideSpec[]` + `RenderMode` + `BrandingConfig`

**Output:** `PreviewSlide[]`
```
- position: int
- html: str                             # Design Mode: rendered HTML
- screenshot_path: str | None           # path to PNG screenshot
- template_fit: TemplateFitReport | None  # Template Mode only
  - fits: bool
  - mismatches: list[PlaceholderMismatch]
```

**Hard rules:**
- Design Mode: every `PlannedSlideSpec` must produce valid HTML. Rendering failures are not silently swallowed.
- Template Mode: if `template_fit.fits == false`, the slide is flagged for Stage 7 (replan).
- Screenshots are produced via headless browser (Playwright/Puppeteer), not LibreOffice conversion.

---

### Stage 6 -- Visual Quality Gate (NEW, HARD BLOCK)

**Replaces:** V2 Stage 4b (preflight, warning-only) + parts of V2 Stage 8 (design review)

**Responsibility:** Evaluate each preview slide against visual quality criteria. Slides below threshold are blocked from export and sent to Stage 7 for replanning.

**Input:** `PreviewSlide[]`

**Output:** `QualityGateResult`
```
- slide_verdicts: list[SlideVerdict]
  - position: int
  - score: float                        # 0-100
  - passed: bool                        # score >= threshold (75)
  - failures: list[QualityFailure]
    - rule: str                         # e.g., "TEXT_OVERFLOW", "EMPTY_ZONE", "CONTRAST_RATIO"
    - severity: Severity                # block, warn
    - message: str
    - zone_id: str | None
- deck_passed: bool                     # all slides passed
- blocked_slides: list[int]             # positions that must be replanned
```

**Quality rules (hard block if violated):**
- TEXT_OVERFLOW: any zone's rendered text exceeds its bounding box
- EMPTY_ZONE: a required zone has no content
- CONTRAST_RATIO: text-on-background contrast below WCAG AA (4.5:1)
- WORD_BUDGET_EXCEEDED: any zone exceeds its `max_words` budget
- DUPLICATE_CONTENT: two slides have > 80% text overlap

**Quality rules (warning, no block):**
- VISUAL_BALANCE: heavy asymmetry in multi-element layouts
- FONT_SIZE_VARIATION: excessive font size differences within a slide
- WHITESPACE_RATIO: too little or too much whitespace

**Hard rules:**
- If `deck_passed == false`, the pipeline MUST enter Stage 7. It cannot skip to Stage 8.
- A slide with any `severity == block` failure cannot be exported.
- The quality gate can be run using either Vision AI analysis (screenshot -> Gemini Vision) or rule-based DOM inspection. Rule-based is preferred for speed; Vision AI is used as a second opinion for borderline cases.

---

### Stage 7 -- Replan / Auto-Repair

**Replaces:** V2 Stage 4 (auto-fixes + LLM regeneration) + V2 Stage 8 (design review fixes)

**Responsibility:** Fix slides that failed the quality gate. The repair scope is intentionally limited to prevent infinite loops.

**Input:** `QualityGateResult` + `PlannedSlideSpec[]` (blocked slides only)

**Output:** `PlannedSlideSpec[]` (repaired) -- fed back to Stage 5 for re-preview

**Allowed repair actions:**
1. **Shorten text:** Reduce word count in overflowing zones
2. **Reduce points:** Remove lowest-emphasis `CompressedPoint` items
3. **Switch layout variant:** Change variant within the same layout family (e.g., `card_grid_3` -> `card_grid_2`)
4. **Remove/replace visual:** Drop an image that causes layout issues
5. **Split slide:** Break one slide into two (last resort)

**Forbidden repair actions:**
- Change layout family (that requires going back to Stage 4)
- Add new content not present in the compressed spec
- Change the core assertion
- Re-run the LLM for free-form content generation

**Hard rules:**
- Maximum 2 replan iterations per slide. If a slide fails after 2 repairs, it is removed from the deck and logged.
- Maximum 1 split per repair cycle (prevents slide count explosion).
- After repair, the slide goes back through Stage 5 (preview) and Stage 6 (gate). It must pass before reaching Stage 8.

---

### Stage 8 -- Final Render

**Replaces:** V2 Stage 7 (PPTX Rendering)

**Responsibility:** Convert gate-passed slides into the final output format.

**Input:** `PreviewSlide[]` (only slides with `passed == true`) + `RenderMode`

**Output:** Final file path

**Design Mode workflow:**
1. Take the HTML preview slides that passed the quality gate
2. Convert HTML -> PPTX using a DOM-to-PPTX bridge (maps HTML elements to python-pptx shapes with matching positions, sizes, fonts, and colors)
3. Embed generated images and charts
4. Write final `.pptx` file

**Template Mode workflow:**
1. Load the corporate `.pptx` template
2. For each slide, map `PlannedSlideSpec` zones to template placeholders using the template's `.profile.json`
3. Fill placeholders using pptx-automizer (deterministic, no coordinate math)
4. Preserve template master slides, themes, and branding
5. Write final `.pptx` file

**Hard rules:**
- Only slides that passed Stage 6 are rendered. No exceptions.
- Design Mode: the PPTX output must visually match the HTML preview within 95% fidelity.
- Template Mode: no shapes are created outside of template placeholders. All content goes into existing placeholders or is omitted.

---

### Stage 9 -- Deck-Level Review

**Replaces:** Parts of V2 Stage 8 (design review, but now at deck level instead of slide level)

**Responsibility:** Review the complete deck for consistency, rhythm, and narrative flow. This is the final quality check before delivery.

**Input:** Final `.pptx` file + `PresentationPlan`

**Output:** `DeckReviewReport`
```
- overall_score: float                  # 0-100
- passed: bool                          # score >= 70
- findings: list[DeckFinding]
  - category: str                       # STYLE_CONSISTENCY, SLIDE_RHYTHM, TITLE_QUALITY, REDUNDANCY, STORYLINE_FLOW
  - severity: Severity
  - message: str
  - affected_slides: list[int]
```

**Review criteria:**
- **Style consistency:** Font sizes, colors, and spacing should be uniform across the deck
- **Slide rhythm:** No more than 3 consecutive text-heavy slides; visual slides should be interspersed
- **Title quality:** No duplicate titles; titles should not be generic ("Overview", "Summary")
- **Redundancy:** Flag slides with > 60% content overlap
- **Storyline flow:** The narrative arc from Stage 2 should be reflected in the final slide order

**Hard rules:**
- This stage is advisory, not blocking. The deck has already passed per-slide quality gates in Stage 6.
- Findings are returned to the user as improvement suggestions, not applied automatically.
- If `overall_score < 50`, a warning is surfaced in the UI recommending the user review the deck.

---

## Layout Families and Hard Budgets

V3 reduces slide types from 14 to 7 layout families. Each family has strict per-zone word budgets that are enforced at Stage 4 (planning) and Stage 6 (quality gate).

### hero

Opening or emphasis slide with a strong visual statement.

| Zone | Max Words | Notes |
|------|-----------|-------|
| title | 8 | Short, punchy, no sentences |
| subtitle | 15 | One supporting line |
| visual | 1 (hero image or none) | Full-bleed or right-half |
| bullets | 0 | No bullets allowed |

**Variants:** `hero_image_right`, `hero_image_fullbleed`, `hero_text_only`

### section-divider

Visual break between major chapters.

| Zone | Max Words | Notes |
|------|-----------|-------|
| title | 6 | Chapter name only |
| subtitle | 12 | Optional context line |
| visual | 0 | No images |
| bullets | 0 | No bullets |

**Variants:** `divider_centered`, `divider_left_aligned`

### timeline

Chronological or sequential events.

| Zone | Max Words | Notes |
|------|-----------|-------|
| title | 8 | Slide headline |
| entries | 3-6 | Number of timeline entries |
| entry_title | 5 per entry | Short label |
| entry_description | 12 per entry | One-line description |

**Variants:** `timeline_horizontal`, `timeline_vertical`, `timeline_compact`

### card-grid

Multi-point content in balanced card layout.

| Zone | Max Words | Notes |
|------|-----------|-------|
| title | 8 | Slide headline |
| cards | 2-4 | Number of cards |
| card_title | 4 per card | Short label |
| card_body | 15 per card | Supporting text |

**Variants:** `card_grid_2`, `card_grid_3`, `card_grid_4`

### comparison

Side-by-side comparison of two options, states, or categories.

| Zone | Max Words | Notes |
|------|-----------|-------|
| title | 8 | Slide headline |
| columns | 2 | Exactly 2 columns |
| column_items | max 4 per column | Bullet-style items |
| item_text | 10 per item | Short comparison point |

**Variants:** `comparison_equal`, `comparison_winner` (highlights one side)

### key-fact

Single dominant number, KPI, or insight.

| Zone | Max Words | Notes |
|------|-----------|-------|
| title | 8 | Slide headline |
| dominant_value | 1 | The number or KPI |
| supporting_facts | max 2 | Secondary data points |
| fact_text | 8 per fact | Brief label |

**Variants:** `key_fact_single`, `key_fact_with_chart`, `key_fact_with_trend`

### closing

Final slide with summary and call to action.

| Zone | Max Words | Notes |
|------|-----------|-------|
| title | 8 | Closing headline |
| takeaways | max 3 | Key takeaway bullets |
| takeaway_text | 12 per takeaway | One sentence each |

**Variants:** `closing_takeaways`, `closing_cta`, `closing_contact`

---

## Comparison: V2 vs V3

| Aspect | V2 | V3 |
|--------|----|----|
| Slide types | 14 | 7 layout families |
| Text budgets | Post-hoc char limits | Per-zone word budgets, enforced at planning |
| Content compression | None | Dedicated Stage 3 |
| Quality gate | Warning-only (Stage 4b) | Hard block (Stage 6) |
| Preview | None | HTML preview before export (Stage 5) |
| Design review | Post-render cosmetic fixes (Stage 8) | Pre-render gate + post-render deck review (Stages 6, 9) |
| Template handling | Same pipeline with `template_id` flag | Separate Template Mode branch |
| Layout engine | Fixed blueprint lookup | Content-aware zone mapping |
| Render target | Direct python-pptx | HTML -> PPTX bridge (Design Mode) or pptx-automizer (Template Mode) |
| Repair scope | Truncation + LLM regeneration | Constrained repair actions, max 2 iterations |
