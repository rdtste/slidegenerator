# ADR-005: Technology Stack — Python-first Hybrid

## Status
Accepted

## Date
2026-04-01

## Context
We evaluated three stack options:
- **Option A**: Python-first (migrate NestJS to Python)
- **Option B**: Hybrid Python + TypeScript (current architecture, evolved)
- **Option C**: Shift to TypeScript/Node.js

## Decision
**Option B: Python-first Hybrid** — keep the existing architecture, evolve it.

### Python (PPTX Service) is responsible for:
- PPTX rendering (python-pptx — no JS equivalent of similar quality)
- Template analysis and profiling (lxml, OOXML parsing)
- LLM pipeline orchestration (structured output, Pydantic validation)
- Image generation (Vertex AI Imagen 3.0)
- Chart generation (matplotlib)
- Visual QA (LibreOffice + Gemini Vision)
- All PPTX-domain logic

### TypeScript/NestJS (Backend) is responsible for:
- API gateway and routing
- Chat orchestration (Clarity Engine, multi-turn briefing)
- Export job management (SSE streaming, progress, download)
- Template CRUD (upload, scope management)
- Frontend communication
- Authentication/authorization (future)

### Rationale
1. **python-pptx has no JavaScript equivalent** — `pptxgenjs` cannot read/analyze existing templates, cannot fill placeholders, lacks OOXML-level control
2. **The existing architecture works** — Multi-container Cloud Run deployment is stable
3. **Each language plays to its strengths** — Python for document processing, TypeScript for API/UI
4. **Migration risk is zero** — No technology change required
5. **Both ecosystems have strong LLM support** — Vertex AI SDKs exist for both

## Consequences
- Two container images to maintain (existing)
- Template sync between services needed (existing, can be improved)
- Shared types defined in both languages (Pydantic + TypeScript interfaces)
- Future features choose the appropriate service based on domain

## Alternatives Rejected
- **Python-only**: Would require rebuilding NestJS chat/SSE/job infrastructure
- **TypeScript-only**: Would require rebuilding PPTX rendering with inferior tools
