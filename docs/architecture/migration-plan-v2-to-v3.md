# Migration Plan: V2 to V3 Pipeline

Phased migration from the current V2 pipeline to the V3 architecture. V2 remains operational throughout; V3 is built alongside it and activated via feature flag.

---

## Phase 1 -- Foundation (Week 1-2)

### Prerequisites
- V2 pipeline is stable and deployed
- Team has reviewed `current-v2-assessment.md` and `target-pipeline-v3.md`
- Development environment supports both Python 3.12+ and Node.js 22+

### Deliverables

#### 1.1 Shared Domain Models

Create `pptx-service/app/schemas/v3_models.py` with all V3 Pydantic models:

```python
class RenderMode(str, Enum):
    DESIGN = "design"
    TEMPLATE = "template"

class PresentationRequest(BaseModel):
    topic: str
    goal: str
    audience: Audience
    purpose: PresentationPurpose
    render_mode: RenderMode
    branding: BrandingConfig
    source_content: str
    requested_slide_count: int
    language: str
    constraints: list[str]

class SlideIntent(BaseModel):
    position: int
    narrative_role: NarrativeRole
    core_assertion: str                 # max 20 words
    supporting_points: list[str]        # max 3
    data_hint: DataHint | None
    visual_hint: VisualHint | None

class CompressedSlideSpec(BaseModel):
    position: int
    core_assertion: str                 # max 15 words
    compressed_points: list[CompressedPoint]
    data_payload: DataPayload | None
    compression_ratio: float
    split_from: int | None

class PlannedSlideSpec(BaseModel):
    position: int
    layout_family: LayoutFamily
    layout_variant: str
    visual_role: VisualRole
    zones: list[ContentZone]
    data_payload: DataPayload | None
    budget_utilization: float

class ContentZone(BaseModel):
    zone_id: str
    content: str
    max_words: int
    actual_words: int
```

#### 1.2 RenderMode Enum and Routing

Add `RenderMode` to the API layer. The V3 orchestrator checks `render_mode` and branches into Design Mode or Template Mode at Stage 5.

```python
# New API endpoint alongside existing V2
POST /api/v1/generate-v3   # SSE, accepts render_mode field
```

#### 1.3 Content Compressor Module

Create `pptx-service/app/pipeline/content_compressor.py`:

- Input: `PresentationPlan` (from Stage 2)
- Output: `CompressedSlideSpec[]`
- LLM-based compression with explicit word budgets in the prompt
- Slide splitting logic for content that exceeds budget after compression
- Unit tests with sample inputs at various verbosity levels

#### 1.4 Visual Review Engine Interface

Create `pptx-service/app/pipeline/visual_review.py`:

```python
class VisualReviewEngine(Protocol):
    async def evaluate(self, slides: list[PreviewSlide]) -> QualityGateResult: ...

class RuleBasedReview(VisualReviewEngine):
    """DOM/zone-based quality checks. Fast, deterministic."""

class VisionAIReview(VisualReviewEngine):
    """Gemini Vision-based analysis. Slower, catches visual issues rules miss."""
```

#### 1.5 Hard Quality Gate Scaffolding

Create `pptx-service/app/pipeline/quality_gate.py`:

- Defines `QualityGateResult`, `SlideVerdict`, `QualityFailure` models
- Implements the 5 hard-block rules (TEXT_OVERFLOW, EMPTY_ZONE, CONTRAST_RATIO, WORD_BUDGET_EXCEEDED, DUPLICATE_CONTENT)
- Implements the 3 warning rules (VISUAL_BALANCE, FONT_SIZE_VARIATION, WHITESPACE_RATIO)
- Gate returns `deck_passed: bool` and `blocked_slides: list[int]`
- Unit tests with mock preview data

#### 1.6 V2 Continues Running

- V2 endpoint (`/api/v1/generate-v2`) is unchanged
- V3 endpoint (`/api/v1/generate-v3`) is added alongside
- Frontend gets a feature flag toggle: "Pipeline V3 (experimental)"
- No V2 code is modified in this phase

### Risk Mitigation
- **Risk:** V3 models are incompatible with V2 data structures.
  **Mitigation:** V3 models are in a separate file (`v3_models.py`). V2 models in `models.py` are untouched. Adapter functions convert between them where needed.

- **Risk:** Content compressor LLM calls add latency.
  **Mitigation:** Compressor runs in parallel per slide (like V2 Stage 5). Budget: max 3s per slide.

### Rollback Strategy
- Delete `v3_models.py`, `content_compressor.py`, `visual_review.py`, `quality_gate.py`
- Remove `/api/v1/generate-v3` route
- No V2 code was touched; nothing to restore

---

## Phase 2 -- Design Mode (Week 3-4)

### Prerequisites
- Phase 1 complete: domain models, content compressor, quality gate scaffolding
- Node.js 22+ available in the build environment
- Playwright installed for headless browser screenshots

### Deliverables

#### 2.1 TypeScript Render Service

Create a new service: `render-service/` (Node.js + TypeScript):

```
render-service/
  src/
    components/           # React/Tailwind slide components
      HeroSlide.tsx
      SectionDividerSlide.tsx
      TimelineSlide.tsx
      CardGridSlide.tsx
      ComparisonSlide.tsx
      KeyFactSlide.tsx
      ClosingSlide.tsx
    renderer/
      html-renderer.ts    # PlannedSlideSpec -> HTML string
      screenshot.ts       # HTML -> PNG via Playwright
      pptx-bridge.ts      # HTML elements -> python-pptx instructions
    server.ts             # Express server, called by pptx-service
  package.json
  tsconfig.json
  Dockerfile
```

The render service runs as a sidecar alongside the pptx-service. Communication is via HTTP on localhost.

#### 2.2 Seven Layout Family Components

Each layout family is a React/Tailwind component that:
- Accepts a `PlannedSlideSpec` as props
- Renders to a 1920x1080px viewport (matches 33.867x19.05cm at 144 DPI)
- Enforces word budgets visually (text that exceeds budget is visually flagged, not silently overflowed)
- Supports multiple variants via props

Component structure per family:
```tsx
interface SlideProps {
  spec: PlannedSlideSpec;
  branding: BrandingConfig;
  variant: string;
}
```

#### 2.3 HTML Preview Composition

Wire Stage 5 (Design Mode) into the V3 orchestrator:
1. V3 orchestrator sends `PlannedSlideSpec[]` to render-service via HTTP
2. Render-service produces HTML for each slide
3. Render-service takes screenshots via Playwright
4. V3 orchestrator receives `PreviewSlide[]` with HTML and screenshot paths

#### 2.4 Browser Screenshot Pipeline

```
PlannedSlideSpec -> React component -> HTML string -> Playwright page.setContent() -> page.screenshot() -> PNG
```

- Viewport: 1920x1080
- Screenshots stored in temp directory, cleaned up after pipeline run
- Timeout: 5s per slide, 30s total

#### 2.5 DOM-to-PPTX Export Bridge

The bridge maps HTML elements to python-pptx shapes:

| HTML Element | PPTX Equivalent |
|-------------|-----------------|
| `<h1>`, `<h2>` | TextBox with title formatting |
| `<p>` | TextBox with body formatting |
| `<ul><li>` | TextBox with bullet formatting |
| `<div>` with background | Rectangle shape with fill |
| `<img>` | Picture shape |
| `<svg>` (chart) | Picture shape (rasterized) |

The bridge reads element positions from the React component's CSS grid/flexbox layout (computed via Playwright `element.boundingBox()`) and maps them to cm coordinates on the PPTX canvas.

#### 2.6 Visual Review as Gatekeeper

Connect the quality gate (from Phase 1) to the preview screenshots:
1. After Stage 5 produces screenshots, Stage 6 runs the quality gate
2. Rule-based review checks zone budgets, contrast, overflow
3. For borderline cases (score 65-75), Vision AI review is run as tiebreaker
4. Failed slides enter Stage 7 (replan), then re-preview and re-gate
5. Only gate-passed slides reach Stage 8 (final render)

### Risk Mitigation
- **Risk:** React/Tailwind components don't match PPTX output fidelity.
  **Mitigation:** Use a fixed set of font stacks (system fonts available in both browser and PowerPoint). Test with side-by-side comparison of HTML preview and PPTX output for each layout family.

- **Risk:** Playwright adds significant latency to the pipeline.
  **Mitigation:** Screenshots are taken in parallel (all slides at once). Budget: 10s for full deck. If Playwright is unavailable, fall back to rule-based-only quality gate (no screenshots).

- **Risk:** Render service adds deployment complexity (another container).
  **Mitigation:** Render service runs as a sidecar in the same Cloud Run multi-container setup. It shares the same lifecycle as the pptx-service.

### Rollback Strategy
- Disable V3 feature flag in frontend; users fall back to V2
- Render service sidecar can be removed from `service-backend.yaml` without affecting V2
- No V2 code was modified

---

## Phase 3 -- Template Mode (Week 5-6)

### Prerequisites
- Phase 2 complete: Design Mode is functional end-to-end
- At least 3 corporate templates available for testing
- Template `.profile.json` files exist (from existing V2 template learning)

### Deliverables

#### 3.1 Template Analysis Module

Extract and expand template analysis from the current `services/template_profiling.py` into a dedicated module:

```
pptx-service/app/templates/
  analyzer.py             # Deep template analysis: placeholders, zones, constraints
  profile.py              # TemplateProfile model with placeholder mapping
  validator.py            # Validate PlannedSlideSpec against template constraints
  versioning.py           # Template version tracking and compatibility checks
```

The analyzer produces a `TemplateProfile` that maps each template slide layout to:
- Available placeholder names and types (title, body, picture, chart)
- Placeholder positions and sizes (from the template XML)
- Text capacity per placeholder (estimated from font size and box dimensions)
- Required vs optional placeholders

#### 3.2 pptx-automizer Integration

Replace direct python-pptx shape creation with pptx-automizer for template filling:

```python
# Instead of:
txBox = slide.shapes.add_textbox(left, top, width, height)

# Use:
from pptx_automizer import fill_placeholder
fill_placeholder(slide, placeholder_name="title", text=zone.content)
```

pptx-automizer handles:
- Finding placeholders by name or index
- Preserving template formatting (fonts, colors, sizes)
- Fitting text to placeholder dimensions
- Handling missing placeholders gracefully

#### 3.3 Deterministic Placeholder Mapping

Create a mapping layer between V3 `ContentZone` IDs and template placeholder names:

```python
ZONE_TO_PLACEHOLDER = {
    "title": ["Title 1", "Title", "Titel"],
    "subtitle": ["Subtitle 2", "Subtitle", "Untertitel"],
    "body": ["Content Placeholder 3", "Text Placeholder 3", "Body"],
    "card_0_title": ["Text Placeholder 4"],
    # ...
}
```

The mapping is:
1. First, try exact match from `TemplateProfile`
2. Then, try fuzzy match from `ZONE_TO_PLACEHOLDER`
3. If no match, skip the zone and log a warning

#### 3.4 Template Versioning

Track template versions to handle updates:

```python
class TemplateVersion(BaseModel):
    template_id: str
    version: int
    file_hash: str                      # SHA-256 of the .pptx file
    profile_hash: str                   # SHA-256 of the .profile.json
    created_at: datetime
    placeholder_map: dict[str, str]     # zone_id -> placeholder_name
```

When a template file changes:
1. Detect via file hash comparison
2. Re-run analyzer to produce new profile
3. Increment version
4. Log breaking changes (removed placeholders, changed sizes)

#### 3.5 Template Fit Validation

Stage 5 (Template Mode) validates that each `PlannedSlideSpec` fits within the template:

```python
class TemplateFitReport(BaseModel):
    fits: bool
    mismatches: list[PlaceholderMismatch]

class PlaceholderMismatch(BaseModel):
    zone_id: str
    issue: MismatchType                 # MISSING_PLACEHOLDER, TEXT_TOO_LONG, TYPE_MISMATCH, NO_IMAGE_PLACEHOLDER
    detail: str
```

If a slide does not fit, it is flagged for Stage 7 (replan) with constrained repair actions:
- Shorten text to fit placeholder capacity
- Remove zones that have no matching placeholder
- Switch to a different template layout that has the required placeholders

### Risk Mitigation
- **Risk:** pptx-automizer does not support all placeholder types.
  **Mitigation:** Fall back to direct python-pptx manipulation for unsupported placeholders. Log which placeholders needed fallback for future library patches.

- **Risk:** Corporate templates have inconsistent placeholder naming.
  **Mitigation:** The analyzer uses both name-based and index-based matching. The `ZONE_TO_PLACEHOLDER` mapping includes common German and English placeholder names.

- **Risk:** Template updates break existing placeholder mappings.
  **Mitigation:** Template versioning detects changes and re-profiles. Breaking changes (removed placeholders) are logged as warnings, and the pipeline falls back to available placeholders.

### Rollback Strategy
- Template Mode in V3 can be disabled independently of Design Mode
- Existing V2 template handling continues to work via `/api/v1/generate-v2`
- Template profiles and versions are stored alongside templates; deleting versioning data does not affect template files

---

## Phase 4 -- Quality Gate and Cutover (Week 7-8)

### Prerequisites
- Phase 2 (Design Mode) and Phase 3 (Template Mode) are functional
- V3 pipeline has been tested with at least 20 diverse prompts
- Side-by-side comparison infrastructure is ready (V2 vs V3 output)

### Deliverables

#### 4.1 Hard Block Implementation

Upgrade the quality gate from Phase 1 scaffolding to production:

- Connect rule-based review to actual DOM measurements (from Playwright)
- Connect Vision AI review to actual screenshots
- Implement the 5 hard-block rules with production thresholds:
  - TEXT_OVERFLOW: detected via Playwright `element.scrollHeight > element.clientHeight`
  - EMPTY_ZONE: detected via zone content check
  - CONTRAST_RATIO: computed from CSS colors
  - WORD_BUDGET_EXCEEDED: computed from `ContentZone.actual_words` vs `max_words`
  - DUPLICATE_CONTENT: computed via text similarity (Jaccard or cosine)
- Tune pass threshold: start at 70, adjust based on A/B results

#### 4.2 Replan Engine

Implement Stage 7 with the full repair action set:

```python
class ReplanEngine:
    async def repair(
        self,
        blocked_slides: list[PlannedSlideSpec],
        failures: list[QualityFailure],
    ) -> list[PlannedSlideSpec]:
        for slide, failure in zip(blocked_slides, failures):
            if failure.rule == "TEXT_OVERFLOW":
                slide = self._shorten_zone(slide, failure.zone_id)
            elif failure.rule == "WORD_BUDGET_EXCEEDED":
                slide = self._reduce_points(slide)
            elif failure.rule == "EMPTY_ZONE":
                slide = self._fill_or_remove_zone(slide, failure.zone_id)
            # ... etc.
        return repaired_slides
```

- Max 2 iterations per slide
- Slides that fail after 2 repairs are removed and logged
- Repair actions are logged for observability

#### 4.3 Deck-Level Review (Stage 9)

Implement the final deck review:

- Style consistency: check font sizes and colors across all slides
- Slide rhythm: flag sequences of 4+ text-heavy slides
- Title quality: flag duplicate or generic titles ("Overview", "Summary", "Agenda")
- Redundancy: flag slides with > 60% text overlap (using word-level Jaccard similarity)
- Storyline flow: verify that `narrative_role` progression matches the `narrative_arc`

Output is advisory: returned to the user as improvement suggestions.

#### 4.4 A/B Comparison: V2 vs V3

Run both pipelines on 50 diverse prompts and compare:

| Metric | Measurement Method |
|--------|--------------------|
| Text overflow rate | Count slides where text exceeds visual bounds |
| Content density | Average words per slide |
| Layout appropriateness | Human rating (1-5) on slide type selection |
| Visual consistency | Standard deviation of font sizes across deck |
| Pipeline latency | Wall-clock time from input to output |
| User preference | Blind A/B test with 5 users |

Acceptance criteria for V3 cutover:
- Text overflow rate: V3 < 5% (V2 baseline: ~40%)
- Content density: V3 avg < 40 words/slide (V2 baseline: ~65 words/slide)
- Layout appropriateness: V3 avg > 4.0 (V2 baseline: ~3.2)
- Pipeline latency: V3 < 2x V2 latency
- User preference: V3 preferred in > 70% of blind comparisons

#### 4.5 Deprecate V2 Pipeline

Once A/B criteria are met:

1. Set V3 as default pipeline in frontend (remove feature flag)
2. Keep V2 endpoint active but add deprecation warning in response headers
3. Log V2 usage for 2 weeks to track remaining consumers
4. After 2 weeks with zero V2 usage:
   - Remove V2 route from API
   - Remove V2-specific code from orchestrator (keep shared utilities)
   - Archive V2 models, blueprints, and prompts in a `v2-archive/` directory
   - Update CLAUDE.md to reflect V3 as the only pipeline

### Risk Mitigation
- **Risk:** V3 quality gate is too strict, rejecting too many slides.
  **Mitigation:** Start with pass threshold at 70 (not 75). Monitor rejection rate during A/B phase. Adjust threshold based on false-positive rate.

- **Risk:** V3 pipeline is significantly slower than V2 due to HTML rendering + screenshots.
  **Mitigation:** Parallelize screenshot generation. Cache React component renders. If latency exceeds 2x V2, consider dropping Vision AI review for all slides and using it only for random sampling.

- **Risk:** Deprecating V2 breaks existing integrations.
  **Mitigation:** The external API (`POST /api/v1/export/generate-deck`) is pipeline-agnostic; it calls whichever pipeline is configured. Switching the default does not change the API contract. The `generate-v2` and `generate-v3` internal endpoints are not exposed externally.

### Rollback Strategy
- Revert frontend default to V2 (one config change)
- V2 endpoint and code are still present until the final cleanup step
- The final cleanup step (archiving V2 code) can be reverted via git if needed within the 2-week monitoring window

---

## Timeline Summary

| Week | Phase | Key Milestone |
|------|-------|---------------|
| 1 | Foundation | V3 domain models, content compressor, quality gate scaffolding |
| 2 | Foundation | Visual review interface, V3 API endpoint, feature flag |
| 3 | Design Mode | Render service, 7 React components, HTML preview |
| 4 | Design Mode | Screenshot pipeline, DOM-to-PPTX bridge, quality gate wired |
| 5 | Template Mode | Template analyzer, pptx-automizer integration |
| 6 | Template Mode | Placeholder mapping, template versioning, fit validation |
| 7 | Quality Gate | Hard block production, replan engine, deck review |
| 8 | Cutover | A/B comparison, V3 default, V2 deprecation begins |

---

## Dependency Graph

```
Phase 1 (Foundation)
  |
  +-- v3_models.py ──────────────────┐
  |                                  |
  +-- content_compressor.py ─────────+──> Phase 2 (Design Mode)
  |                                  |      |
  +-- quality_gate.py ───────────────+      +──> Phase 4 (Quality Gate + Cutover)
  |                                  |      |
  +-- visual_review.py ─────────────-+      |
                                     |      |
                                     +──> Phase 3 (Template Mode)
                                            |
                                            +──> Phase 4
```

Phase 2 and Phase 3 can run in parallel if the team has sufficient capacity. Phase 4 requires both Phase 2 and Phase 3 to be complete.
