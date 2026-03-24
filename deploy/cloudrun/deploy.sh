#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────
# Cloud Run Deployment Script for Slidegenerator
# Deployt 3 Services: frontend, backend, pptx-service
# ──────────────────────────────────────────────────────────────
set -euo pipefail

# ── Configuration ─────────────────────────────────────────────
PROJECT_ID="${GCP_PROJECT:-rd-cmpd-prod513-psl-mate-dev}"
REGION="europe-west1"
REPO="cloud-run-images"
REGISTRY="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}"
PREFIX="slidegenerator"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

# ── Farben ────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()  { echo -e "${GREEN}[INFO]${NC} $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1" >&2; }

# ── Pre-Flight ────────────────────────────────────────────────
check_prerequisites() {
    info "Prüfe Voraussetzungen..."

    if ! command -v gcloud &>/dev/null; then
        error "gcloud CLI nicht installiert."
        exit 1
    fi

    if ! command -v docker &>/dev/null; then
        error "Docker nicht installiert oder nicht gestartet."
        exit 1
    fi

    gcloud config set project "${PROJECT_ID}" --quiet 2>/dev/null

    if [[ ! -f "${REPO_ROOT}/backend/.env" ]]; then
        error "backend/.env fehlt!"
        exit 1
    fi
    if [[ ! -f "${REPO_ROOT}/pptx-service/.env" ]]; then
        error "pptx-service/.env fehlt!"
        exit 1
    fi

    info "Projekt: ${PROJECT_ID} | Region: ${REGION}"
    info "Registry: ${REGISTRY}"
    info "Voraussetzungen OK ✓"
}

# ── Docker Auth ───────────────────────────────────────────────
configure_docker_auth() {
    info "Konfiguriere Docker-Authentifizierung..."
    gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet 2>/dev/null
    info "Docker Auth ✓"
}

# ── Build & Push Images ──────────────────────────────────────
build_and_push() {
    local service="$1"
    local context="$2"
    local image="${REGISTRY}/${PREFIX}-${service}:latest"

    info "Baue ${service}..."
    docker build --platform linux/amd64 -t "${image}" "${context}"

    info "Pushe ${service}..."
    docker push "${image}"

    info "${service} → ${image} ✓"
}

# ── Env vars aus .env laden ───────────────────────────────────
load_env_as_flags() {
    local env_file="$1"
    local flags=""
    while IFS='=' read -r key value; do
        [[ -z "${key}" || "${key}" =~ ^# ]] && continue
        # PORT ist in Cloud Run reserviert — überspringen
        [[ "${key}" == "PORT" || "${key}" == "HOST" ]] && continue
        # Entferne Anführungszeichen
        value="${value%\"}"
        value="${value#\"}"
        value="${value%\'}"
        value="${value#\'}"
        flags="${flags},${key}=${value}"
    done < "${env_file}"
    # Entferne führendes Komma
    echo "${flags#,}"
}

# ── Deploy Cloud Run Service ─────────────────────────────────
deploy_service() {
    local service="$1"
    local port="$2"
    local image="${REGISTRY}/${PREFIX}-${service}:latest"
    local extra_env="${3:-}"
    local memory="${4:-512Mi}"
    local cpu="${5:-1}"
    local allow_unauth="${6:-true}"

    info "Deploye ${PREFIX}-${service} nach Cloud Run..."

    local min_inst="${7:-0}"
    local concurrency="${8:-80}"

    local cmd=(
        gcloud run deploy "${PREFIX}-${service}"
        --image="${image}"
        --region="${REGION}"
        --port="${port}"
        --memory="${memory}"
        --cpu="${cpu}"
        --min-instances="${min_inst}"
        --max-instances=3
        --concurrency="${concurrency}"
        --timeout=300
        --ingress=internal-and-cloud-load-balancing
        --quiet
    )

    if [[ -n "${extra_env}" ]]; then
        cmd+=(--set-env-vars="${extra_env}")
    fi

    # Org-Policy erlaubt kein "all" ingress — nutze IAM-disabled für öffentlichen Zugang
    if [[ "${allow_unauth}" == "true" ]]; then
        cmd+=(--no-invoker-iam-check)
    else
        cmd+=(--no-allow-unauthenticated)
    fi

    "${cmd[@]}"

    local url
    url=$(gcloud run services describe "${PREFIX}-${service}" \
        --region="${REGION}" \
        --format='value(status.url)')
    info "${PREFIX}-${service} → ${url} ✓"
    echo "${url}"
}

# ── Main ──────────────────────────────────────────────────────
main() {
    echo ""
    info "═══════════════════════════════════════════════"
    info "  Slidegenerator → Cloud Run Deployment"
    info "  Projekt: ${PROJECT_ID}"
    info "  Region:  ${REGION}"
    info "═══════════════════════════════════════════════"
    echo ""

    check_prerequisites
    configure_docker_auth

    # ── 1. Build all images ──
    info "── Schritt 1: Docker Images bauen & pushen ──"
    build_and_push "pptx-service" "${REPO_ROOT}/pptx-service"
    build_and_push "backend"      "${REPO_ROOT}/backend"
    build_and_push "frontend"     "${REPO_ROOT}/frontend"

    # ── 2. Deploy pptx-service (intern) ──
    info "── Schritt 2: pptx-service deployen ──"
    local pptx_env
    pptx_env=$(load_env_as_flags "${REPO_ROOT}/pptx-service/.env")
    local pptx_url
    pptx_url=$(deploy_service "pptx-service" "8000" "${pptx_env}" "2Gi" "2" "false" "1" "1")

    # ── 3. Deploy backend (intern) ──
    info "── Schritt 3: backend deployen ──"
    local backend_env
    backend_env=$(load_env_as_flags "${REPO_ROOT}/backend/.env")
    # Override PPTX_SERVICE_URL mit der Cloud Run URL
    backend_env="${backend_env},PPTX_SERVICE_URL=${pptx_url}"
    local backend_url
    backend_url=$(deploy_service "backend" "3000" "${backend_env}" "512Mi" "1" "false")

    # ── 4. Update frontend nginx.conf für Cloud Run ──
    info "── Schritt 4: Frontend vorbereiten ──"
    # Erstelle eine Cloud Run-spezifische nginx.conf
    cat > "${REPO_ROOT}/frontend/nginx.cloudrun.conf" << NGINX_EOF
server {
    listen 8080;
    server_name _;
    root /usr/share/nginx/html;
    index index.html;

    location / {
        try_files \$uri \$uri/ /index.html;
    }

    location /api/ {
        proxy_pass ${backend_url};
        proxy_set_header Host ${backend_url#https://};
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_ssl_server_name on;
        proxy_read_timeout 300s;
        proxy_send_timeout 300s;
        client_max_body_size 50m;

        # SSE Support
        proxy_buffering off;
        proxy_cache off;
        proxy_set_header Connection '';
        chunked_transfer_encoding off;
    }
}
NGINX_EOF

    # Erstelle Cloud Run-spezifisches Dockerfile
    cat > "${REPO_ROOT}/frontend/Dockerfile.cloudrun" << 'DOCKER_EOF'
FROM node:22-slim AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npx ng build --configuration production

FROM nginx:alpine
COPY --from=build /app/dist/frontend/browser /usr/share/nginx/html
COPY nginx.cloudrun.conf /etc/nginx/conf.d/default.conf
EXPOSE 8080
DOCKER_EOF

    # Build mit Cloud Run Dockerfile
    local frontend_image="${REGISTRY}/${PREFIX}-frontend:latest"
    info "Baue Frontend mit Cloud Run Config..."
    docker build --platform linux/amd64 \
        -t "${frontend_image}" \
        -f "${REPO_ROOT}/frontend/Dockerfile.cloudrun" \
        "${REPO_ROOT}/frontend"
    docker push "${frontend_image}"

    # ── 5. Deploy frontend (öffentlich) ──
    info "── Schritt 5: frontend deployen ──"
    local frontend_url
    frontend_url=$(deploy_service "frontend" "8080" "" "256Mi" "1" "true")

    # ── 6. Backend muss Frontend als erlaubten Origin kennen ──
    # (Falls CORS konfiguriert ist)

    # ── Aufräumen ──
    rm -f "${REPO_ROOT}/frontend/nginx.cloudrun.conf"
    rm -f "${REPO_ROOT}/frontend/Dockerfile.cloudrun"

    # ── Ergebnis ──
    echo ""
    info "═══════════════════════════════════════════════"
    info "  Deployment abgeschlossen!"
    info "═══════════════════════════════════════════════"
    info ""
    info "  Frontend:     ${frontend_url}"
    info "  Backend:      ${backend_url}"
    info "  PPTX-Service: ${pptx_url}"
    info ""
    info "  Öffne im Browser: ${frontend_url}"
    info "═══════════════════════════════════════════════"
}

main "$@"
