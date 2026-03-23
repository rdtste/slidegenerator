#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────
# Teardown: löscht die GCE-VM und Firewall-Regel
# ──────────────────────────────────────────────────────────────
set -euo pipefail

PROJECT_ID="${GCP_PROJECT:-rd-cmpd-prod513-psl-mate-dev}"
ZONE="europe-west3-a"
INSTANCE_NAME="slidegenerator"
NETWORK_TAG="slidegenerator-http"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()  { echo -e "${GREEN}[INFO]${NC} $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }

gcloud config set project "${PROJECT_ID}" --quiet

echo ""
warn "Dies löscht die VM '${INSTANCE_NAME}' und alle darauf gespeicherten Daten!"
read -rp "Fortfahren? (y/N): " confirm
if [[ ! "${confirm}" =~ ^[Yy]$ ]]; then
    info "Abgebrochen."
    exit 0
fi

info "Lösche VM '${INSTANCE_NAME}'..."
gcloud compute instances delete "${INSTANCE_NAME}" \
    --zone="${ZONE}" --quiet 2>/dev/null || true

info "Lösche Firewall-Regel '${NETWORK_TAG}'..."
gcloud compute firewall-rules delete "${NETWORK_TAG}" \
    --quiet 2>/dev/null || true

info "Teardown abgeschlossen ✓"
