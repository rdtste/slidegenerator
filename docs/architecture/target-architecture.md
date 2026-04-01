# Target Architecture

## Core Concept: Dual-Mode Presentation Generation

```
                     PresentationRequest
                     (mode, content, template_id?)
                            │
                     ┌──────┴──────┐
                     │  Orchestrator │
                     └──────┬──────┘
                   ┌────────┴────────┐
                   ▼                 ▼
           ┌──────────────┐  ┌──────────────┐
           │  Design Mode  │  │ Template Mode │
           │  (AI Pipeline)│  │(Deterministic)│
           └──────┬───────┘  └──────┬───────┘
                  │                  │
           ┌──────┴───────┐  ┌──────┴───────┐
           │DesignRenderer │  │TemplRenderer  │
           │(Blueprints +  │  │(Placeholder   │
           │ Theme-aware)  │  │ Mapping)      │
           └──────┬───────┘  └──────┬───────┘
                  │                  │
                  └────────┬────────┘
                           ▼
                     presentation.pptx
```

## Design Mode
- Goal: Visually excellent presentations (Gamma.app quality)
- AI generates storyline, content, and slide planning
- Blueprint-based layout with template theme integration
- Custom typography hierarchy with auto-fitting
- Image generation (Imagen 3.0) and chart rendering (matplotlib)
- Visual QA loop for design review
- Template optional — provides colors/fonts, not layout constraints

## Template Mode
- Goal: Robust, deterministic corporate template filling
- Upload → Analyze → Register → Fill
- Uses template's actual placeholders (TITLE, BODY, OBJECT, PICTURE)
- Structured placeholder mapping from analyzed profile
- Content validation against layout constraints
- No LLM for layout decisions — mapping is deterministic
- Template required — defines all visual aspects

## Shared Foundation

### Unified Content Model
Both modes share the same content representation:
- `PresentationSpec` — the full presentation definition
- `SlideSpec` — per-slide content
- `ContentBlock` variants — bullets, KPIs, quotes, etc.
- `Visual` — image/chart specifications

### Template Registry
Central registry for all templates:
- `TemplateDescriptor` — metadata, version, analyzed profile
- `TemplateVersion` — versioned snapshots
- `PlaceholderMapping` — analyzed slot assignments per layout

### Rendering Interface
Protocol-based rendering:
- `PresentationRenderer` — base protocol
- `DesignModeRenderer` — blueprint + theme rendering
- `TemplateModeRenderer` — placeholder-based filling
- Both produce valid PPTX via python-pptx

## Module Structure

```
pptx-service/app/
├── api/                          # API routes (existing)
├── domain/                       # Core domain models
│   ├── models.py                 # GenerationMode, PresentationRequest
│   ├── content_model.py          # Unified content model
│   └── interfaces.py             # Protocols/ABCs
├── generation/                   # Generation orchestration
│   ├── orchestrator.py           # Mode-aware orchestrator
│   ├── design_mode/              # Design Mode pipeline
│   │   ├── pipeline.py
│   │   └── prompts/
│   └── template_mode/            # Template Mode pipeline
│       ├── pipeline.py
│       └── slot_mapper.py
├── templates/                    # Template management
│   ├── registry.py               # Template registry
│   ├── analyzer.py               # Deep template analysis
│   ├── storage.py                # Storage abstraction
│   └── models.py                 # Template domain models
├── rendering/                    # Rendering engines
│   ├── base.py                   # Renderer protocol
│   ├── design_renderer.py        # Design mode renderer
│   ├── template_renderer.py      # Template mode renderer
│   └── typography.py             # Shared typography system
├── layouts/                      # Blueprint system (existing)
├── schemas/                      # Pydantic schemas (existing)
├── services/                     # Supporting services (existing)
├── slide_types/                  # Slide type definitions (existing)
└── validators/                   # Validation rules (existing)
```

## Technology Decisions

| Concern | Technology | Reason |
|---------|-----------|--------|
| PPTX Rendering | python-pptx | Best OOXML manipulation library |
| LLM | Gemini via Vertex AI | Existing integration, structured JSON output |
| Images | Imagen 3.0 | Existing integration, high quality |
| Charts | matplotlib | Existing integration, customizable |
| API Gateway | NestJS | Existing, chat orchestration, SSE |
| Template Analysis | python-pptx + lxml | Direct OOXML access |
| Visual QA | Gemini Vision | Existing integration |

## API Evolution

Current → Target:
- `POST /generate-v2` → `POST /generate` (unified, with `mode` parameter)
- `POST /generate` (V1) → deprecated, then removed
- Template endpoints remain, enhanced with versioning
- External API (`generate-deck`) gains `mode` parameter

## Non-Goals
- No HTML/React intermediate rendering layer
- No migration away from python-pptx
- No replacement of NestJS backend
- No multi-database setup (filesystem + JSON remains)
