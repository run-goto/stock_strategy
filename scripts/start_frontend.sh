#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-python}"
FRONTEND_HOST="${FRONTEND_HOST:-127.0.0.1}"
FRONTEND_PORT="${FRONTEND_PORT:-8080}"

echo "Starting frontend: http://${FRONTEND_HOST}:${FRONTEND_PORT}"
exec "$PYTHON_BIN" -m http.server "$FRONTEND_PORT" --bind "$FRONTEND_HOST" --directory frontend
