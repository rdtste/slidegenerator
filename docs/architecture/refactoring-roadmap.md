# Refactoring Roadmap

## Phased Migration Plan

All phases are incremental. Each phase produces working, deployable code.
Existing functionality is never removed until its replacement is stable.

---

## Phase 1: Foundation (Risk: Low)

**Goal:** Establish domain models, interfaces, and module structure without changing existing behavior.

### Tasks
1. Create `domain/` module with core models (`GenerationMode`, `PresentationRequest`)
2. Define rendering protocols (`PresentationRenderer`, `TemplateAnalyzer`, `SlidePlanner`)
3. Create `templates/` module structure (registry, analyzer, storage interfaces)
4. Introduce `TemplateDescriptor` model alongside existing `.meta.json`
5. Create unified `GenerateRequest` model with `mode` parameter
6. Wire new orchestrator that delegates to existing V1/V2 based on mode

### Acceptance Criteria
- New modules exist with clean interfaces
- Existing V1 and V2 pipelines continue to work unchanged
- New orchestrator can dispatch to V1 or V2 based on mode
- No breaking changes to any API endpoint

---

## Phase 2: Template Mode (Risk: Medium)

**Goal:** Build robust corporate template filling using analyzed template profiles.

### Tasks
1. Refactor `profile_service.py` into `templates/analyzer.py`
2. Create `PlaceholderMapping` — structured slot assignment per layout
3. Implement `TemplateModeRenderer` wrapping existing `pptx_service.py` logic
4. Replace `_REWE_LAYOUT_MAP` with dynamic mapping from template profile
5. Add template versioning on upload
6. Implement `slot_mapper.py` — maps content blocks to template placeholders
7. Add content validation against layout constraints

### Acceptance Criteria
- Template Mode produces correct PPTX using analyzed placeholder mappings
- No hardcoded template-specific layout maps remain
- Templates can be re-uploaded without losing previous versions
- Content that exceeds layout constraints is truncated with warnings

### Affected Files
- `pptx-service/app/services/pptx_service.py` — extract rendering logic
- `pptx-service/app/services/profile_service.py` — refactor into templates/
- `pptx-service/app/renderers/pptx_renderer_v2.py` — remove `_REWE_LAYOUT_MAP`
- `backend/src/templates/templates.service.ts` — add versioning

---

## Phase 3: Design Mode (Risk: Medium)

**Goal:** Upgrade visual quality toward Gamma.app-level output.

### Tasks
1. Integrate template ColorDNA into Design Mode renderer
2. Extend Blueprint system with template-dimension awareness
3. Improve typography hierarchy (larger contrast between levels)
4. Add whitespace control system (global grid, padding rules)
5. Improve auto-fitting with better text metrics
6. Enhance Design Review Agent with stricter quality rules
7. Add theme-aware shape styling (rounded corners, shadows, gradients)

### Acceptance Criteria
- Design Mode output uses template colors/fonts when template is provided
- Blueprints adapt to different slide dimensions (16:9 vs 4:3)
- Typography hierarchy produces visually distinct levels
- Visual QA catches spacing/alignment violations

### Affected Files
- `pptx-service/app/renderers/pptx_renderer_v2.py` — theme integration
- `pptx-service/app/layouts/blueprints.py` — dimension awareness
- `pptx-service/app/layouts/engine.py` — whitespace system
- `pptx-service/app/services/design_review_agent.py` — quality rules

---

## Phase 4: API Hardening (Risk: Low)

**Goal:** Stabilize API for external consumers and operational reliability.

### Tasks
1. Unify generation endpoints (single `/generate` with `mode`)
2. Add request validation (template exists, mode-template consistency)
3. Add idempotency for `generate-deck` API
4. Improve error responses with structured error codes
5. Add request logging and tracing (correlation IDs)
6. Document API with OpenAPI schema
7. Add health check with dependency status

### Acceptance Criteria
- Single unified generation endpoint serves both modes
- External API validates all inputs before starting jobs
- Error responses include actionable error codes
- API documentation is auto-generated from code

### Affected Files
- `pptx-service/app/api/routes/generate_v2.py` — unify
- `pptx-service/app/api/routes/generate.py` — deprecate
- `backend/src/export/export.controller.ts` — unified start endpoint
- `backend/src/export/export.dto.ts` — unified DTO

---

## Timeline Estimate

| Phase | Duration | Parallelizable |
|-------|----------|----------------|
| Phase 1: Foundation | 1-2 weeks | No (prerequisite) |
| Phase 2: Template Mode | 2-3 weeks | With Phase 3 |
| Phase 3: Design Mode | 2-3 weeks | With Phase 2 |
| Phase 4: API Hardening | 1-2 weeks | After Phase 2+3 |
