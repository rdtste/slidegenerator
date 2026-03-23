#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────
# Teardown: löscht alle Cloud Run Services
# ──────────────────────────────────────────────────────────────
set -euo pipefail

PROJECT_ID="${GCP_PROJECT:-rd-cmpd-prod513-psl-mate-dev}"
REGION="europe-west1"
PREFIX="slidegenerator"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()  { echo -e "${GREEN}[INFO]${NC} $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }

gcloud config set project "${PROJECT_ID}" --quiet 2>/dev/null

echo ""
warn "Dies löscht alle 3 Cloud Run Services (${PREFIX}-frontend, -backend, -pptx-service)!"
read -rp "Fortfahren? (y/N): " confirm
if [[ ! "${confirm}" =~ ^[Yy]$ ]]; then
    info "Abgebrochen."
    exit 0
fi

for svc in frontend backend pptx-service; do
    info "Lösche ${PREFIX}-${svc}..."
    gcloud run services delete "${PREFIX}-${svc}" \
        --region="${REGION}" --quiet 2>/dev/null || true
done

info "Teardown abgeschlossen ✓"
