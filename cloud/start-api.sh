#!/usr/bin/env bash
set -euo pipefail

PORT="${PORT:-8080}"
HOST="${HOST:-0.0.0.0}"

exec uvicorn api:app --host "$HOST" --port "$PORT"
