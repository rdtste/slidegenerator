# Slidegenerator — Prompt-to-PowerPoint Generator

Generiert professionelle PowerPoint-Präsentationen aus natürlicher Sprache,
basierend auf ausgewählten Folienmastern. Cloud-native Microservice-Architektur
mit Angular, NestJS und Kubernetes.

## Architektur

```
┌─────────────────────────────────────────────────┐
│          Angular Frontend (nginx)                │
│  Chat │ Markdown Editor │ Marp Preview │ Export  │
└──────────────────┬──────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────┐
│          NestJS API Gateway (Node.js)            │
│  • POST /api/v1/chat      → LLM → Markdown      │
│  • POST /api/v1/preview   → Marp Core → HTML     │
│  • GET  /api/v1/templates → Template-Verwaltung   │
│  • POST /api/v1/export    → PPTX / PDF / HTML    │
└──────────┬─────────────────────┬────────────────┘
           │                     │
┌──────────▼─────┐   ┌──────────▼──────────────┐
│  marp-cli      │   │  Python PPTX Service     │
│  (PDF/HTML)    │   │  (FastAPI + python-pptx)  │
│  im Backend    │   │  Folienmaster → PPTX      │
└────────────────┘   └─────────────────────────┘
```

## Schnellstart (Lokal)

```bash
# 1. Backend starten
cd backend
cp .env.example .env   # API-Key eintragen
npm install
npm run start:dev

# 2. PPTX-Service starten
cd pptx-service
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# 3. Frontend starten
cd frontend
npm install
ng serve
```

Öffne http://localhost:4200

## Docker Compose

```bash
cp backend/.env.example backend/.env  # API-Key eintragen
docker compose up --build
```

Frontend: http://localhost:4200 | Backend: http://localhost:3000 | PPTX-Service: http://localhost:8000

## Kubernetes (Helm)

```bash
# Images bauen
docker build -t slidegenerator-frontend ./frontend
docker build -t slidegenerator-backend ./backend
docker build -t slidegenerator-pptx-service ./pptx-service

# Helm installieren
helm install slidegenerator ./k8s/slidegenerator \
  --set backend.env.OPENAI_API_KEY=sk-your-key
```

## Projektstruktur

```
slidegenerator/
├── frontend/              # Angular 21 (Standalone Components, Signals)
│   └── src/app/
│       ├── features/      # Chat, Editor, Preview, ExportPanel
│       └── core/          # Services, Models
├── backend/               # NestJS (API Gateway)
│   └── src/
│       ├── chat/          # LLM Integration (OpenAI)
│       ├── preview/       # Marp Core → HTML Preview
│       ├── templates/     # Template Upload/Verwaltung
│       └── export/        # PPTX (via Python), PDF/HTML (via marp-cli)
├── pptx-service/          # FastAPI + python-pptx
│   └── app/
│       └── services/      # Markdown Parser, PPTX Generator, Templates
├── k8s/slidegenerator/            # Helm Chart
│   └── templates/         # Deployments, Services, Ingress, PVC
└── docker-compose.yml
```

## Tech-Stack

| Schicht | Technologie |
|---|---|
| Frontend | Angular 21, SCSS, Signals, Standalone Components |
| API Gateway | NestJS, TypeScript, @marp-team/marp-core |
| PPTX-Service | FastAPI, python-pptx, Pydantic |
| Preview | @marp-team/marp-core (HTML), marp-cli (PDF) |
| Container | Docker, nginx |
| Orchestrierung | Kubernetes, Helm |
