# Slidegenerator — Prompt-to-PowerPoint

Generiert professionelle PowerPoint-Prasentationen aus natuerlicher Sprache. KI-gestuetzter Workflow mit Gemini, Template-Learning und automatischer Qualitaetskontrolle.

## Architektur

```
User  ->  Angular Frontend (nginx)
            |
            +-> /api/*  ->  NestJS Backend (:3000)
                              |
                              +-> Vertex AI Gemini (LLM fuer Folien + Template-Analyse)
                              +-> Marp Core / CLI (HTML-Preview + PDF-Export)
                              +-> Python PPTX Service (:8000)
                                    |
                                    +-> python-pptx (PPTX-Generierung)
                                    +-> Vertex AI Imagen 3.0 (KI-Bilder)
                                    +-> matplotlib (Diagramme)
                                    +-> Gemini Vision QA (Qualitaetskontrolle)
```

## Features

- **Chat-basierte Folienerstellung** — Multi-Turn-Dialog mit "Clarity Engine" Moderator
- **Template-Learning** — KI analysiert Folienmaster (Farb-DNA, Typografie, Layout-Katalog)
- **KI-Bildgenerierung** — Vertex AI Imagen 3.0 mit automatischem Placeholder-Fitting
- **Diagramme** — Bar, Line, Pie, Donut, Stacked Bar, Horizontal Bar via matplotlib
- **Gemini Vision QA-Loop** — Automatische Qualitaetskontrolle nach Generierung mit programmatischen Korrekturen
- **Zielgruppen-Anpassung** — Team, Management, Casual
- **Dokumenten-Upload** — PDF, DOCX, TXT, MD als Quelldaten
- **Live-Preview** — Marp-basierte HTML-Vorschau mit Inline-Editor
- **SSE-Progress** — Echtzeit-Fortschritt bei Export und QA

## Schnellstart (Lokal)

### Voraussetzungen

- Node.js 22+
- Python 3.12+
- GCP-Projekt mit aktivierter Vertex AI API
- `gcloud auth application-default login`

### Services starten

```bash
# 1. Backend
cd backend
cp .env.example .env    # GCP-Projekt und Region eintragen
npm install
npm run start:dev       # Port 3000

# 2. PPTX-Service
cd pptx-service
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# 3. Frontend
cd frontend
npm install
ng serve                # Port 4200
```

Oeffne http://localhost:4200

## Docker Compose

```bash
# Lokale Entwicklung
docker compose up --build
# Frontend: :4200 | Backend: :3000 | PPTX-Service: :8000

# Produktion (GCE)
docker compose -f docker-compose.prod.yml up --build
# Frontend: :80 (nginx reverse-proxy)
```

GCP-Credentials werden als Volume gemountet — siehe `docker-compose.yml`.

## Deployment

### Google Compute Engine

```bash
cd deploy/gce
./deploy.sh              # Erstellt VM + Firewall + Service Account
./redeploy.sh            # Aktualisiert ohne VM-Neuerstellung
./teardown.sh            # Aufraeumen
```

### Cloud Run

```bash
cd deploy/cloudrun
./deploy.sh              # Baut Images, pusht zu Artifact Registry, deployed 3 Services
./teardown.sh
```

### Kubernetes (Helm)

```bash
helm install slidegenerator ./k8s/slidegenerator
```

Konfiguration in `k8s/slidegenerator/values.yaml` (2 Replicas, nginx Ingress, 1Gi PVC).

## Projektstruktur

```
slidegenerator/
+-- frontend/                # Angular 21 (Signals, Zoneless, Standalone)
|   +-- src/app/
|       +-- features/        # Chat, Editor, Preview, ExportPanel, Settings
|       +-- core/            # ApiService, ChatState, Models
+-- backend/                 # NestJS 11 (API Gateway)
|   +-- src/
|       +-- chat/            # Clarity Engine, Gemini-Integration
|       +-- preview/         # Marp HTML-Rendering
|       +-- templates/       # Upload, Learning, Analyse
|       +-- export/          # Async PPTX-Export (SSE), PDF via marp-cli
|       +-- settings/        # GCP-Konfiguration
+-- pptx-service/            # FastAPI + python-pptx
|   +-- app/
|       +-- services/
|           +-- pptx_service.py         # PPTX-Generierung
|           +-- markdown_service.py     # Markdown -> SlideContent
|           +-- image_service.py        # Imagen 3.0 Bildgenerierung
|           +-- chart_service.py        # matplotlib Diagramme
|           +-- image_fitting.py        # Bild-Cropping fuer Placeholder
|           +-- gemini_vision_qa.py     # Gemini Vision Analyse
|           +-- pptx_fixer.py           # Programmatische PPTX-Korrekturen
|           +-- qa_loop_service.py      # QA-Fix-Loop Orchestrierung
|           +-- template_service.py     # Template-Verwaltung
|           +-- profile_service.py      # Deep Template Profiling
+-- deploy/                  # GCE + Cloud Run Deployment-Scripts
+-- k8s/                     # Helm Chart
+-- docker-compose.yml       # Lokale Entwicklung
+-- docker-compose.prod.yml  # Produktion
```

## Workflow

1. **Chat**: User beschreibt Praesentation (optional mit Datei-Upload)
2. **Klaerung**: Clarity Engine fuehrt Beratungsgespraech (Fokus, Folienanzahl, Gliederung)
3. **Generierung**: Gemini erstellt strukturiertes Markdown mit Layout-Annotationen
4. **Validierung**: Backend prueft Struktur + Overflow, Auto-Fix via Gemini
5. **Preview**: Marp-HTML-Vorschau, Inline-Editing pro Folie
6. **Export**: PPTX-Generierung mit KI-Bildern + Diagrammen auf Template-Layouts
7. **QA-Loop**: Gemini Vision analysiert jede Folie, programmatische Korrekturen (max 2 Runden)
8. **Download**: Fertige PPTX (oder PDF)

## QA-Loop (Gemini Vision)

Nach der PPTX-Generierung laeuft automatisch eine Qualitaetskontrolle:

```
PPTX generiert
  -> LibreOffice konvertiert zu PDF
  -> pdftoppm erstellt JPEG pro Folie (150 DPI)
  -> Gemini Vision analysiert jedes Bild:
     - Text-Overflow, Bild-Overflow, leere Placeholder
     - Ueberlappungen, Kontrast, Layout-Fehler
  -> Programmatische Fixes via python-pptx:
     - Bilder resizen/croppen
     - Text kuerzen
     - Placeholder-Text entfernen
     - Elemente repositionieren
  -> Re-Check nur geaenderter Folien
  -> Maximal 2 Iterationen
```

Der Fortschritt wird per SSE live im Frontend angezeigt.

## Template-Learning

Templates koennen per UI hochgeladen und "angelernt" werden:

1. **Upload**: .pptx/.potx Datei hochladen (max 50 MB)
2. **Profiling**: Extrahiert Farb-DNA, Typografie, Layout-Katalog, Placeholder-Dimensionen
3. **KI-Klassifizierung**: Gemini klassifiziert Layouts (title, content, image, chart, etc.)
4. **Constraints**: Maximale Bullets, Zeichenlimits pro Layout werden berechnet
5. **Ergebnis**: `.profile.json` wird gespeichert, alle Generierungen nutzen diese Regeln

## API-Uebersicht

### Backend (NestJS, Port 3000)

| Methode | Endpoint | Beschreibung |
|---------|----------|-------------|
| POST | /api/v1/chat | Folien generieren |
| POST | /api/v1/chat/clarify | Klaerungsdialog |
| POST | /api/v1/preview | HTML-Preview |
| GET | /api/v1/templates | Templates auflisten |
| POST | /api/v1/templates | Template hochladen |
| POST | /api/v1/templates/:id/learn | Template anlernen |
| POST | /api/v1/export/start | Async PPTX-Export starten |
| SSE | /api/v1/export/progress/:jobId | Export-Fortschritt |
| GET | /api/v1/export/download/:jobId | Export herunterladen |
| GET/PUT | /api/v1/settings | LLM-Einstellungen |

### PPTX-Service (FastAPI, Port 8000)

| Methode | Endpoint | Beschreibung |
|---------|----------|-------------|
| POST | /api/v1/generate | Sync PPTX-Generierung |
| POST | /api/v1/generate-stream | SSE PPTX-Generierung + QA |
| GET | /api/v1/download/:fileId | PPTX herunterladen |
| POST | /api/v1/templates/:id/learn | Template-Profil extrahieren |
| GET | /api/v1/templates/:id/theme | Visuelles Theme |
| GET | /api/v1/templates/:id/structure | Layout-Struktur |

## Tech-Stack

| Schicht | Technologie |
|---------|-------------|
| Frontend | Angular 21, Signals, Zoneless, SCSS |
| Backend | NestJS 11, TypeScript, OpenAI SDK (Vertex AI) |
| PPTX-Service | FastAPI, python-pptx, Pydantic v2 |
| LLM | Google Vertex AI Gemini (2.5 Pro/Flash) |
| Bilder | Vertex AI Imagen 3.0 |
| QA | Gemini Vision, LibreOffice, Poppler |
| Preview | Marp Core (HTML), Marp CLI (PDF) |
| Diagramme | matplotlib, numpy |
| Container | Docker, nginx |
| Deployment | Docker Compose, Cloud Run, GCE, Kubernetes/Helm |

## Umgebungsvariablen

### Backend (.env)

```
GCP_PROJECT_ID=your-project-id
GCP_REGION=europe-west1
GEMINI_MODEL=gemini-2.5-flash
PPTX_SERVICE_URL=http://localhost:8000
TEMPLATES_DIR=./templates
```

### PPTX-Service (.env)

```
GCP_PROJECT_ID=your-project-id
GCP_REGION=europe-west1
IMAGEN_MODEL=imagen-3.0-generate-002
GEMINI_MODEL=gemini-2.5-flash
QA_MAX_ITERATIONS=2
```
