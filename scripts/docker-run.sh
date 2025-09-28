#!/usr/bin/env bash
set -euo pipefail

# docker-run-dev.sh — Run the vecapi container
# Usage:
#   scripts/docker-run-dev.sh [TAG] [HOST_PORT]
# Examples:
#   scripts/docker-run-dev.sh                 # runs vecapi:latest on 8010 -> 8000
#   scripts/docker-run-dev.sh vecapi:latest 9000
#
# It will load environment variables from .env in the repo root by default.
# To use a different env file, set ENV_FILE path env var before running:
#   ENV_FILE=./.env.sandbox scripts/docker-run-dev.sh

TAG="${1:-vecapi:latest}"
HOST_PORT="${2:-8010}"
ENV_FILE="${ENV_FILE:-.env}"

if [ ! -f "$ENV_FILE" ]; then
  echo "[docker-run] Warning: env file '$ENV_FILE' not found. Continuing without --env-file."
  USE_ENV_FILE=false
else
  USE_ENV_FILE=true
fi

CMD=(docker run --rm -p "${HOST_PORT}:8000")
if [ "$USE_ENV_FILE" = true ]; then
  CMD+=(--env-file "$ENV_FILE")
fi
CMD+=("${TAG}")

echo "[docker-run] Running: ${CMD[*]}"
"${CMD[@]}"