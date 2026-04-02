# Phase 4 — Quality Gate, Replan Engine & Deck Review

**Duration:** Week 7-8
**Goal:** Build the full quality pipeline with hard blocks, automatic replanning, deck-level consistency review, and a V2-to-V3 comparison framework.

---

## Context

Phases 1-3 introduced the domain models, content compression, rendering service, and template mode. Phase 4 completes the V3 pipeline by finalizing the quality gate (upgrading the basic version from Phase 1), building the full replan engine, adding deck-level review, and establishing the path to deprecate V2.

---

## Tasks

### 1. Finalize visual review engine

**File:** `pptx-service/app/quality/visual_review_engine.py` (new) or `rendering-service/src/renderer/visual_review.ts` (enhance from Phase 2)

Complete all scoring dimensions:

| Dimension | Weight | Measurement |
|---|---|---|
| Text density | 25% | Characters per cm^2 of text area; penalize > 4 chars/cm^2 |
| Visual hierarchy | 20% | Title font size vs body font size ratio; expect >= 1.5x |
| Whitespace balance | 20% | Margin utilization; penalize < 5% or > 40% empty space |
| Element alignment | 15% | Deviation from grid lines; penalize > 2mm misalignment |
| Font consistency | 10% | Number of distinct font sizes; penalize > 3 sizes per slide |
| Color compliance | 10% | All colors within the theme palette; penalize off-palette colors |

Optional Vision AI pass:
- Send screenshot to Gemini Vision with scoring rubric
- Use as tie-breaker when rule-based score is borderline (65-75 range)
- Do not use as primary score (too slow, too variable)

### 2. Implement full replan engine

**File:** `pptx-service/app/quality/replan_engine.py` (enhance from Phase 1)

Add all remediation strategies, applied in order of least disruption:

**Strategy 1: Content reduction**
- Trigger: text density too high
- Action: re-run content compressor with 70% of original budget
- Expected resolution rate: 60% of blocked slides

**Strategy 2: Layout variant switching**
- Trigger: content reduction insufficient, or visual hierarchy failure
- Action: switch to next-best layout family from the candidate list (from Epic 3)
- Re-run compression with new family's budgets
- Expected resolution rate: 25% of remaining blocked slides

**Strategy 3: Visual removal**
- Trigger: image/chart causes layout overflow
- Action: downgrade visual role (HERO_IMAGE to DECORATIVE_ICON, or remove entirely)
- Reclaim space for text
- Expected resolution rate: 10% of remaining blocked slides

**Strategy 4: Slide splitting**
- Trigger: all above strategies fail
- Action: split slide into two slides, distribute content evenly
- Apply compression to each half independently
- Expected resolution rate: 90% of remaining blocked slides

**Iteration guard:**
- Max 2 iterations per slide
- After 2 iterations, use the highest-scoring attempt
- Attach quality warning to export metadata: `{ slide_index, best_score, warning: "below_threshold" }`

### 3. Implement deck-level review

**File:** `pptx-service/app/quality/deck_review.py`

Run after all individual slides pass their quality gates:

**3a. Style consistency check**
- Verify all slides use the same font family
- Verify title font sizes are identical across slides (allow section dividers to differ)
- Verify body font sizes are identical across slides
- Verify color palette usage is within theme bounds
- Score: 0-100, threshold 80

**3b. Slide rhythm analysis**
- Check that no more than 2 consecutive slides use the same layout family
- Check that the deck opens with HERO and closes with CLOSING
- Check that SECTION_DIVIDER slides appear at logical topic transitions
- Flag sequences of 3+ text-heavy slides without a visual break
- Score: 0-100, threshold 70

**3c. Visual consistency**
- If the deck contains 3+ generated images, check style coherence
- Compare image color temperatures (warm/cool)
- Compare illustration styles (photo vs illustration vs abstract)
- Flag inconsistent styles for regeneration with unified style prompt
- Score: 0-100, threshold 60

**3d. Title quality check**
- Verify all titles are under 8 words
- Verify no duplicate titles exist
- Verify titles follow a consistent grammatical pattern (all noun phrases, or all verb phrases)
- Score: 0-100, threshold 80

**3e. Redundancy detection**
- Compare slide content pairwise using text similarity (cosine similarity on TF-IDF vectors)
- Flag pairs with similarity > 0.7 for merging or differentiation
- Provide specific recommendation: "Slides 4 and 7 cover similar ground — consider merging"

### 4. A/B comparison framework

**File:** `pptx-service/app/quality/ab_comparison.py`

Build a framework for comparing V2 and V3 output:
- Input: same `PresentationRequest`
- Run both V2 and V3 pipelines
- Generate side-by-side screenshots for each slide
- Apply visual review scoring to both versions
- Output: comparison report with per-slide scores and overall averages
- Store results for analysis

### 5. Deprecation path for V2 pipeline

**File:** `pptx-service/app/pipeline/feature_flags.py`

Create feature flag system:
- `PIPELINE_VERSION` flag: `v2` (default), `v3`, `v3_with_fallback`
- `v3_with_fallback`: try V3 first, fall back to V2 on error
- Flag configurable via environment variable and API parameter
- Log pipeline version used for each generation request

Deprecation timeline:
1. Week 7: V3 available behind feature flag (`PIPELINE_VERSION=v3`)
2. Week 8: V3 becomes default (`PIPELINE_VERSION=v3_with_fallback`)
3. Week 10: V2 removed (after 2 weeks of V3 as default with no regressions)

### 6. Production rollout

**Files to modify:**
- `pptx-service/app/config.py` — add feature flag configuration
- `pptx-service/app/api/routes/generate_v2.py` — route to V3 based on flag
- `deploy/cloudrun/service-backend.yaml` — add `PIPELINE_VERSION` env var
- `docker-compose.yml` — add `PIPELINE_VERSION` env var

Rollout steps:
1. Deploy V3 with `PIPELINE_VERSION=v2` (V3 code present but inactive)
2. Enable `v3_with_fallback` for internal testing
3. Monitor error rates and quality scores for 1 week
4. Switch to `v3` as default
5. Remove V2 code after 2 weeks of stable V3

---

## Acceptance Criteria

- [ ] No slide below quality threshold (default 70/100) appears in the exported PPTX.
- [ ] Replan engine resolves 90%+ of blocked slides within 2 iterations.
- [ ] Slides that cannot be resolved are included with a quality warning in export metadata.
- [ ] Deck-level review catches style inconsistencies (font mismatches, color drift) with > 80% precision.
- [ ] Deck-level review catches redundant slides with > 70% precision.
- [ ] A/B comparison shows V3 output scores higher than V2 on average (measured across 20 test prompts).
- [ ] Feature flag system allows gradual rollout without code changes.
- [ ] V2 pipeline continues to work unchanged until explicit removal.
- [ ] All quality modules have pytest test coverage with both passing and failing test cases.
- [ ] Production deployment does not require downtime.

---

## Files Created

| File | Purpose |
|---|---|
| `pptx-service/app/quality/visual_review_engine.py` | Complete visual scoring engine |
| `pptx-service/app/quality/deck_review.py` | Deck-level consistency review |
| `pptx-service/app/quality/ab_comparison.py` | V2 vs V3 comparison framework |
| `pptx-service/app/pipeline/feature_flags.py` | Feature flag system |

## Files Modified

| File | Change |
|---|---|
| `pptx-service/app/quality/replan_engine.py` | Add all remediation strategies |
| `pptx-service/app/config.py` | Add feature flag configuration |
| `pptx-service/app/api/routes/generate_v2.py` | Route based on pipeline version flag |
| `deploy/cloudrun/service-backend.yaml` | Add PIPELINE_VERSION env var |
| `docker-compose.yml` | Add PIPELINE_VERSION env var |
