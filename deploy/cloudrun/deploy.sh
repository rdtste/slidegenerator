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
# Internal custom domain base (used for service-to-service communication)
INTERNAL_DOMAIN="${INTERNAL_DOMAIN:-${PROJECT_ID}.internal.run.rewe.cloud}"

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

    info "Deploye ${PREFIX}-${service} nach Cloud Run..."

    local min_inst="${6:-0}"
    local concurrency="${7:-80}"

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

    # Ingress ist auf internal-and-cloud-load-balancing beschränkt,
    # daher IAM-Check deaktivieren damit Services untereinander kommunizieren können
    cmd+=(--no-invoker-iam-check)

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
    pptx_url=$(deploy_service "pptx-service" "8000" "${pptx_env}" "2Gi" "2" "1" "1")

    # ── 3. Deploy backend (intern) ──
    info "── Schritt 3: backend deployen ──"
    local backend_env
    backend_env=$(load_env_as_flags "${REPO_ROOT}/backend/.env")
    # PPTX_SERVICE_URL muss die interne Custom Domain nutzen,
    # da Cloud Run-zu-Cloud Run Calls über die öffentliche URL als extern gelten
    backend_env="${backend_env},PPTX_SERVICE_URL=https://${PREFIX}-pptx-service.${INTERNAL_DOMAIN}"
    local backend_url
    backend_url=$(deploy_service "backend" "3000" "${backend_env}" "512Mi" "1")

    # ── 4. Build & deploy frontend ──
    info "── Schritt 4: Frontend bauen & deployen ──"
    # Frontend nutzt Dockerfile.cloudrun (statische Dateien, kein API-Proxy)
    # API-Aufrufe gehen direkt vom Browser zum Backend via Custom Domain
    local frontend_image="${REGISTRY}/${PREFIX}-frontend:latest"
    docker build --platform linux/amd64 \
        -t "${frontend_image}" \
        -f "${REPO_ROOT}/frontend/Dockerfile.cloudrun" \
        "${REPO_ROOT}/frontend"
    docker push "${frontend_image}"

    local frontend_url
    frontend_url=$(deploy_service "frontend" "8080" "" "256Mi" "1")

    # Also update the legacy "slidegenerator" service (custom domain target)
    info "Aktualisiere slidegenerator Service (Custom Domain)..."
    gcloud run deploy "${PREFIX}" \
        --image="${frontend_image}" \
        --region="${REGION}" \
        --port=8080 \
        --memory=256Mi \
        --cpu=1 \
        --max-instances=3 \
        --timeout=300 \
        --ingress=internal-and-cloud-load-balancing \
        --no-invoker-iam-check \
        --quiet 2>/dev/null || warn "slidegenerator Service nicht gefunden (nur relevant bei Custom Domain)"
    info "slidegenerator Service aktualisiert ✓"

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
