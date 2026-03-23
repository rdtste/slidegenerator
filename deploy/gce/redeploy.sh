#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────
# Redeploy: aktualisiert die Anwendung auf der bestehenden VM
# Nutze dies nach Code-Änderungen (statt deploy.sh neu auszuführen)
# ──────────────────────────────────────────────────────────────
set -euo pipefail

PROJECT_ID="${GCP_PROJECT:-rd-cmpd-prod513-psl-mate-dev}"
ZONE="europe-west3-a"
INSTANCE_NAME="slidegenerator"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

GREEN='\033[0;32m'; NC='\033[0m'
info() { echo -e "${GREEN}[INFO]${NC} $1"; }

gcloud config set project "${PROJECT_ID}" --quiet

info "Erstelle Archiv..."
tmp_archive="/tmp/slidegenerator-deploy.tar.gz"
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

info "Kopiere auf VM..."
gcloud compute scp "${tmp_archive}" \
    "${INSTANCE_NAME}:~/slidegenerator.tar.gz" \
    --zone="${ZONE}" --quiet

rm -f "${tmp_archive}"

info "Entpacke und starte neu..."
gcloud compute ssh "${INSTANCE_NAME}" --zone="${ZONE}" --command="
    mkdir -p ~/app && \
    tar -xzf ~/slidegenerator.tar.gz -C ~/app && \
    rm ~/slidegenerator.tar.gz && \
    cd ~/app && \
    docker compose -f docker-compose.prod.yml build && \
    docker compose -f docker-compose.prod.yml up -d
"

external_ip=$(gcloud compute instances describe "${INSTANCE_NAME}" \
    --zone="${ZONE}" \
    --format='get(networkInterfaces[0].accessConfigs[0].natIP)')

info "Redeploy abgeschlossen → http://${external_ip}"
