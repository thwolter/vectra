#!/bin/sh

set -e

PORT=${PORT:-8010}

echo "Start app (OTel config from core.settings)"
uv run uvicorn app.main:app --host 0.0.0.0 --port "$PORT" &

echo "Start worker (OTel config from core.settings)"
uv run dramatiq app.worker.actors --processes 1 --threads 1

# Trap to clean up background jobs on Ctrl+C
trap 'jobs -p | xargs -r kill' INT TERM EXIT

wait
