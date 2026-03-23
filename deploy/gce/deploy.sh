#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────
# GCE Deployment Script for Slidegenerator
# Deploys the application on a single GCE VM with Docker Compose
# ──────────────────────────────────────────────────────────────
set -euo pipefail

# ── Configuration ─────────────────────────────────────────────
PROJECT_ID="${GCP_PROJECT:-rd-cmpd-prod513-psl-mate-dev}"
REGION="europe-west3"
ZONE="${REGION}-a"
INSTANCE_NAME="slidegenerator"
MACHINE_TYPE="e2-medium"            # 2 vCPU, 4 GB RAM — ausreichend für 3 Container
DISK_SIZE="30"                      # GB
IMAGE_FAMILY="cos-113-lts"          # Container-Optimized OS
IMAGE_PROJECT="cos-cloud"
NETWORK_TAG="slidegenerator-http"
SERVICE_ACCOUNT_NAME="slidegenerator-sa"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

# ── Farben ────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()  { echo -e "${GREEN}[INFO]${NC} $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1" >&2; }

# ── Pre-Flight Checks ────────────────────────────────────────
check_prerequisites() {
    info "Prüfe Voraussetzungen..."

    if ! command -v gcloud &>/dev/null; then
        error "gcloud CLI nicht installiert. → https://cloud.google.com/sdk/docs/install"
        exit 1
    fi

    # Prüfe ob Projekt existiert und wir Zugang haben
    if ! gcloud projects describe "${PROJECT_ID}" &>/dev/null; then
        error "Kein Zugriff auf Projekt '${PROJECT_ID}'. Bitte 'gcloud auth login' ausführen."
        exit 1
    fi

    gcloud config set project "${PROJECT_ID}" --quiet
    info "Projekt: ${PROJECT_ID}"

    # Prüfe ob .env-Dateien existieren
    if [[ ! -f "${REPO_ROOT}/backend/.env" ]]; then
        error "backend/.env fehlt! Kopiere backend/.env.example und trage die Werte ein."
        exit 1
    fi
    if [[ ! -f "${REPO_ROOT}/pptx-service/.env" ]]; then
        error "pptx-service/.env fehlt!"
        exit 1
    fi

    info "Voraussetzungen OK ✓"
}

# ── APIs prüfen ───────────────────────────────────────────────
enable_apis() {
    info "Prüfe benötigte GCP APIs..."
    local missing=()
    for api in compute.googleapis.com aiplatform.googleapis.com; do
        if ! gcloud services list --enabled --format="value(config.name)" 2>/dev/null | grep -q "${api}"; then
            missing+=("${api}")
        fi
    done

    if [[ ${#missing[@]} -eq 0 ]]; then
        info "Alle benötigten APIs bereits aktiv ✓"
        return 0
    fi

    warn "Fehlende APIs: ${missing[*]}"
    info "Versuche APIs zu aktivieren..."
    gcloud services enable "${missing[@]}" --quiet 2>/dev/null || {
        error "Konnte APIs nicht aktivieren. Bitte einen Projektadmin bitten, diese APIs zu aktivieren:"
        for api in "${missing[@]}"; do
            error "  - ${api}"
        done
        exit 1
    }
    info "APIs aktiviert ✓"
}

# ── Service Account ──────────────────────────────────────────
setup_service_account() {
    local sa_email="${SERVICE_ACCOUNT_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

    if gcloud iam service-accounts describe "${sa_email}" &>/dev/null 2>&1; then
        info "Service Account existiert bereits: ${sa_email}"
    else
        info "Erstelle Service Account..."
        gcloud iam service-accounts create "${SERVICE_ACCOUNT_NAME}" \
            --display-name="Slidegenerator Service Account" \
            --quiet
    fi

    # Vertex AI Berechtigungen (für Gemini + Imagen)
    info "Setze IAM-Berechtigungen..."
    for role in "roles/aiplatform.user"; do
        gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
            --member="serviceAccount:${sa_email}" \
            --role="${role}" \
            --quiet --no-user-output-enabled
    done

    info "Service Account bereit: ${sa_email} ✓"
}

# ── Firewall-Regel ────────────────────────────────────────────
setup_firewall() {
    if gcloud compute firewall-rules describe "${NETWORK_TAG}" &>/dev/null 2>&1; then
        info "Firewall-Regel '${NETWORK_TAG}' existiert bereits"
    else
        info "Erstelle Firewall-Regel für HTTP (Port 80)..."
        gcloud compute firewall-rules create "${NETWORK_TAG}" \
            --allow=tcp:80 \
            --target-tags="${NETWORK_TAG}" \
            --description="Allow HTTP traffic to Slidegenerator" \
            --quiet
    fi
    info "Firewall bereit ✓"
}

# ── VM erstellen ──────────────────────────────────────────────
create_vm() {
    local sa_email="${SERVICE_ACCOUNT_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

    if gcloud compute instances describe "${INSTANCE_NAME}" --zone="${ZONE}" &>/dev/null 2>&1; then
        warn "VM '${INSTANCE_NAME}' existiert bereits in ${ZONE}."
        read -rp "Löschen und neu erstellen? (y/N): " confirm
        if [[ "${confirm}" =~ ^[Yy]$ ]]; then
            gcloud compute instances delete "${INSTANCE_NAME}" \
                --zone="${ZONE}" --quiet
        else
            info "Nutze bestehende VM."
            return 0
        fi
    fi

    info "Erstelle VM '${INSTANCE_NAME}' (${MACHINE_TYPE}) in ${ZONE}..."
    gcloud compute instances create "${INSTANCE_NAME}" \
        --zone="${ZONE}" \
        --machine-type="${MACHINE_TYPE}" \
        --image-family="${IMAGE_FAMILY}" \
        --image-project="${IMAGE_PROJECT}" \
        --boot-disk-size="${DISK_SIZE}GB" \
        --tags="${NETWORK_TAG}" \
        --service-account="${sa_email}" \
        --scopes="cloud-platform" \
        --metadata-from-file=startup-script="${SCRIPT_DIR}/startup.sh" \
        --quiet

    info "VM erstellt ✓"

    # Warte bis SSH bereit ist
    info "Warte auf SSH-Zugang..."
    for i in $(seq 1 30); do
        if gcloud compute ssh "${INSTANCE_NAME}" --zone="${ZONE}" --command="echo ok" &>/dev/null 2>&1; then
            info "SSH bereit ✓"
            return 0
        fi
        sleep 5
    done
    error "SSH-Timeout nach 150s"
    exit 1
}

# ── Code + .env auf die VM kopieren ───────────────────────────
deploy_code() {
    info "Kopiere Anwendung auf die VM..."

    # Erstelle temporäres Archiv (ohne node_modules, .venv, etc.)
    local tmp_archive="/tmp/slidegenerator-deploy.tar.gz"
    tar -czf "${tmp_archive}" \
        -C "${REPO_ROOT}" \
        --exclude='node_modules' \
        --exclude='.venv' \
        --exclude='__pycache__' \
        --exclude='.angular' \
        --exclude='.git' \
        --exclude='dist' \
        --exclude='backend/presentations' \
        .

    # Kopiere Archiv auf VM
    gcloud compute scp "${tmp_archive}" \
        "${INSTANCE_NAME}:~/slidegenerator.tar.gz" \
        --zone="${ZONE}" --quiet

    rm -f "${tmp_archive}"

    # Entpacken und starten
    gcloud compute ssh "${INSTANCE_NAME}" --zone="${ZONE}" --command="
        mkdir -p ~/app && \
        tar -xzf ~/slidegenerator.tar.gz -C ~/app && \
        rm ~/slidegenerator.tar.gz
    "

    info "Code deployt ✓"
}

# ── Docker Compose starten ────────────────────────────────────
start_services() {
    info "Starte Docker Compose auf der VM..."

    gcloud compute ssh "${INSTANCE_NAME}" --zone="${ZONE}" --command="
        cd ~/app && \
        docker compose -f docker-compose.prod.yml down --remove-orphans 2>/dev/null || true && \
        docker compose -f docker-compose.prod.yml build --no-cache && \
        docker compose -f docker-compose.prod.yml up -d
    "

    info "Services gestartet ✓"

    # Warte auf Health
    info "Prüfe Health..."
    sleep 15

    local external_ip
    external_ip=$(gcloud compute instances describe "${INSTANCE_NAME}" \
        --zone="${ZONE}" \
        --format='get(networkInterfaces[0].accessConfigs[0].natIP)')

    info "──────────────────────────────────────────────"
    info "Deployment abgeschlossen!"
    info "URL:  http://${external_ip}"
    info "API:  http://${external_ip}/api/v1/health"
    info "──────────────────────────────────────────────"
}

# ── Main ──────────────────────────────────────────────────────
main() {
    echo ""
    info "═══════════════════════════════════════════════"
    info "  Slidegenerator → GCE Deployment"
    info "  Projekt: ${PROJECT_ID}"
    info "  Zone:    ${ZONE}"
    info "═══════════════════════════════════════════════"
    echo ""

    check_prerequisites
    enable_apis
    setup_service_account
    setup_firewall
    create_vm
    deploy_code
    start_services
}

main "$@"
