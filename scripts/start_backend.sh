#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-python}"
BACKEND_HOST="${BACKEND_HOST:-127.0.0.1}"
BACKEND_PORT="${BACKEND_PORT:-8001}"
BACKEND_RELOAD="${BACKEND_RELOAD:-0}"

args=(main.py --host "$BACKEND_HOST" --port "$BACKEND_PORT")
if [[ "$BACKEND_RELOAD" == "1" || "$BACKEND_RELOAD" == "true" ]]; then
  args+=(--reload)
fi

echo "Starting backend: http://${BACKEND_HOST}:${BACKEND_PORT}"
exec "$PYTHON_BIN" "${args[@]}"
