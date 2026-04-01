# Refactoring Backlog

## Priority Legend
- **P0**: Must have for architecture to work
- **P1**: High value, should be done soon
- **P2**: Important but can wait
- **P3**: Nice to have

---

## P0 — Foundation

| ID | Task | Phase | Risk | Affected Files |
|----|------|-------|------|----------------|
| F-01 | Create `domain/models.py` with GenerationMode, PresentationRequest | 1 | Low | New file |
| F-02 | Create `domain/interfaces.py` with Renderer, Analyzer protocols | 1 | Low | New file |
| F-03 | Create `domain/content_model.py` with unified SlideSpec | 1 | Low | New file |
| F-04 | Create unified orchestrator with mode dispatch | 1 | Low | New file |
| F-05 | Create `templates/registry.py` with TemplateDescriptor | 1 | Low | New file |

## P0 — Template Mode

| ID | Task | Phase | Risk | Affected Files |
|----|------|-------|------|----------------|
| T-01 | Create PlaceholderMapping model | 2 | Low | New file |
| T-02 | Implement slot_mapper.py | 2 | Medium | New file |
| T-03 | Refactor profile_service → templates/analyzer.py | 2 | Medium | profile_service.py |
| T-04 | Implement TemplateModeRenderer | 2 | Medium | pptx_service.py |
| T-05 | Replace _REWE_LAYOUT_MAP with dynamic mapping | 2 | Medium | pptx_renderer_v2.py |
| T-06 | Add template versioning | 2 | Low | templates.service.ts |

## P1 — Design Mode Quality

| ID | Task | Phase | Risk | Affected Files |
|----|------|-------|------|----------------|
| D-01 | Integrate ColorDNA into Design Renderer | 3 | Low | pptx_renderer_v2.py |
| D-02 | Make Blueprints dimension-aware | 3 | Medium | blueprints.py |
| D-03 | Improve typography contrast | 3 | Low | pptx_renderer_v2.py |
| D-04 | Add whitespace control system | 3 | Medium | engine.py |
| D-05 | Enhance Design Review rules | 3 | Low | design_review_agent.py |

## P1 — API

| ID | Task | Phase | Risk | Affected Files |
|----|------|-------|------|----------------|
| A-01 | Unify generation endpoint | 4 | Low | generate_v2.py |
| A-02 | Add request validation | 4 | Low | generate_v2.py |
| A-03 | Add mode parameter to generate-deck API | 4 | Low | export.controller.ts |
| A-04 | Structured error codes | 4 | Low | All routes |

## P2 — Operational

| ID | Task | Phase | Risk | Affected Files |
|----|------|-------|------|----------------|
| O-01 | Request correlation IDs | 4 | Low | main.py, middleware |
| O-02 | OpenAPI documentation | 4 | Low | Routes |
| O-03 | Health check with dependencies | 4 | Low | main.py |
| O-04 | Job cleanup improvements | 4 | Low | job_cleanup_manager.py |

## P3 — Future

| ID | Task | Phase | Risk | Affected Files |
|----|------|-------|------|----------------|
| FU-01 | Multi-brand template groups | Future | Low | templates/ |
| FU-02 | Redis-based job storage | Future | Medium | export.service.ts |
| FU-03 | Tenant/workspace separation | Future | High | All services |
| FU-04 | Template marketplace | Future | Medium | templates/ |
