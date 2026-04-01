# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Prompt-to-PowerPoint app: users describe a presentation in natural language, AI generates structured slides, and the system renders professional PPTX files with images and charts.

Three microservices:
- **Frontend** (Angular 21, port 4200) — chat UI, preview, export controls
- **Backend** (NestJS 11, port 3000, prefix `/api/v1`) — API gateway, LLM orchestration via Vertex AI Gemini, Marp preview/PDF
- **PPTX Service** (FastAPI, port 8000, prefix `/api/v1`) — python-pptx generation, Imagen 3.0 images, matplotlib charts, Gemini Vision QA

## Development Commands

### Frontend (Angular 21)
```bash
cd frontend
npm install
ng serve                    # Dev server on :4200
ng build                    # Production build
ng test                     # Run tests
```

### Backend (NestJS 11)
```bash
cd backend
cp .env.example .env        # First time: set GCP_PROJECT_ID, GCP_REGION
npm install
npm run start:dev           # Dev server with watch on :3000
npm run build               # Production build
npm run lint                # ESLint with auto-fix
npm test                    # Jest tests
npm run test:watch          # Jest in watch mode
npm run test:e2e            # E2E tests (jest --config ./test/jest-e2e.json)
```

### PPTX Service (FastAPI)
```bash
cd pptx-service
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt   # pytest, pytest-asyncio
uvicorn app.main:app --reload --port 8000
pytest                                # Run tests
```

### Docker Compose
```bash
docker compose up --build   # All 3 services: :4200, :3000, :8000
```

## Architecture

### Service Communication
- Frontend → Backend: `/api/v1/*` (proxied via nginx in prod, ng serve proxy in dev)
- Backend → PPTX Service: `http://localhost:8000` (sidecar in Cloud Run, separate container locally)
- Backend → Vertex AI: OpenAI-compatible SDK (`openai` package) pointed at Vertex AI endpoint
- Both backend and pptx-service share a templates volume

### Two Generation Pipelines

**V1 (Marp-based):** Chat → Gemini generates Markdown → Marp renders HTML preview → python-pptx maps to template layouts

**V2 (AI Pipeline):** 8-stage pipeline in `pptx-service/app/pipeline/`:
Interpret → Storyline → Slide Plan → Validate → Fill Content → Layout → Render → Review.
14 slide types defined in `pptx-service/app/slide_types/`. Layouts in `pptx-service/app/layouts/`, renderers in `pptx-service/app/renderers/`.

### Frontend Architecture
- Angular 21 with Signals, Zoneless change detection, Standalone Components (no NgModules)
- No router — wizard-style step navigation
- State management via `ChatState` injectable (Angular Signals)
- Features in `frontend/src/app/features/`: chat, editor, preview, export-panel, settings, template-management
- Shared services in `frontend/src/app/core/`
- Use `afterEveryRender` (not `afterRender`) for render callbacks

### Backend Architecture
- NestJS 11 modules in `backend/src/`: chat, preview, templates, export, settings, presentations
- Chat module: "Clarity Engine" system prompt for multi-turn slide briefing
- Export module: async SSE-based progress tracking with 15s heartbeat for Cloud Run keep-alive
- Templates: file-based storage with `.profile.json` (learned template characteristics)

### PPTX Service Architecture
- FastAPI app in `pptx-service/app/main.py`, routes in `app/api/routes/`
- Services in `app/services/`: pptx generation, image (Imagen 3.0), charts (matplotlib), markdown parsing, template profiling, QA loop
- V2 pipeline code: `app/schemas/` (Pydantic models), `app/pipeline/` (stage orchestration), `app/prompts/` (LLM prompts)
- Config via pydantic-settings in `app/config.py`
- QA loop: LibreOffice → PDF → JPEG → Gemini Vision analysis → programmatic fixes (max 2 iterations)

## Key Conventions

- Language: codebase comments and docs are in German; code identifiers are in English
- LLM integration: Gemini via Vertex AI using OpenAI-compatible SDK (backend) and direct HTTP/google-auth (pptx-service)
- All API endpoints prefixed with `/api/v1`
- Backend test files: `*.spec.ts` (Jest + ts-jest)
- PPTX Service tests: `pptx-service/tests/` (pytest + pytest-asyncio)
- Frontend formatting: Prettier with `printWidth: 100`, `singleQuote: true`, Angular HTML parser

## Environment

Requires:
- Node.js 22+, Python 3.12+
- GCP project with Vertex AI API enabled
- `gcloud auth application-default login` for local dev
