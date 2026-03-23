#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────
# GCE Startup Script — wird beim ersten Boot der VM ausgeführt.
# Installiert Docker + Docker Compose auf Container-Optimized OS.
# ──────────────────────────────────────────────────────────────
set -euo pipefail

# COS hat Docker vorinstalliert — prüfe ob docker compose plugin da ist
if docker compose version &>/dev/null 2>&1; then
    echo "[startup] Docker Compose already available"
    exit 0
fi

# Fallback für ältere COS-Versionen: installiere Compose als standalone
COMPOSE_VERSION="v2.29.1"
COMPOSE_URL="https://github.com/docker/compose/releases/download/${COMPOSE_VERSION}/docker-compose-$(uname -s)-$(uname -m)"

echo "[startup] Installing Docker Compose ${COMPOSE_VERSION}..."
mkdir -p /usr/local/lib/docker/cli-plugins
curl -fsSL "${COMPOSE_URL}" -o /usr/local/lib/docker/cli-plugins/docker-compose
chmod +x /usr/local/lib/docker/cli-plugins/docker-compose

echo "[startup] Docker Compose installed: $(docker compose version)"
