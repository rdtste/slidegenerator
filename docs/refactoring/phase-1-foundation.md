# Phase 1: Foundation

## Goal
Establish domain models, interfaces, and module structure without changing existing behavior.

## Work Packages

### F-01: Domain Models
**Create `pptx-service/app/domain/models.py`**

Introduce:
- `GenerationMode` enum (DESIGN, TEMPLATE)
- `PresentationRequest` — unified request model for both modes
- `GenerationResult` — unified result model

Does NOT replace existing schemas — wraps them with a mode-aware layer.

### F-02: Rendering Interfaces
**Create `pptx-service/app/domain/interfaces.py`**

Define Python protocols for:
- `PresentationRenderer` — renders a presentation spec to PPTX
- `TemplateAnalyzer` — analyzes a template file
- `SlidePlanner` — plans slide structure from content
- `ContentMapper` — maps content to template slots

### F-03: Unified Content Model
**Create `pptx-service/app/domain/content_model.py`**

Bridge between V1 `PresentationData`/`SlideContent` and V2 `PresentationPlan`/`SlidePlan`:
- `PresentationSpec` — template-agnostic presentation definition
- Converters from V1 and V2 models to PresentationSpec

### F-04: Mode-Aware Orchestrator
**Create `pptx-service/app/generation/orchestrator.py`**

- Accepts `PresentationRequest` with mode
- Dispatches to existing V1 pipeline (for template mode) or V2 pipeline (for design mode)
- Wraps results in unified `GenerationResult`
- Progress callback interface unchanged

### F-05: Template Registry
**Create `pptx-service/app/templates/registry.py`**

- `TemplateDescriptor` model with id, name, version, profile reference
- `TemplateRegistry` class that reads/writes descriptors
- Initially reads from existing `.meta.json` files
- Adds `version` field to metadata

## Acceptance Criteria
- [ ] `domain/` module importable without errors
- [ ] Existing V1 and V2 pipelines unaffected
- [ ] `GenerationMode.DESIGN` dispatches to V2 pipeline
- [ ] `GenerationMode.TEMPLATE` dispatches to V1 pipeline
- [ ] Template registry can list all templates with descriptors
- [ ] No breaking changes to any API

## Risk: Low
All new code, no modifications to existing modules.
