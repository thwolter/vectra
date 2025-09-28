#!/bin/sh
# Local development runner: start API and worker with OpenTelemetry instrumentation
# Web service_name: vecapi-api, Worker service_name: vecapi-worker

set -e

PORT=${PORT:-8010}

# Start FastAPI (Uvicorn) with OTEL instrumentation
uv run opentelemetry-instrument \
  --service_name vecapi-api \
  uvicorn app.main:app --host 0.0.0.0 --port "$PORT" &

# Start Dramatiq worker with OTEL instrumentation
uv run opentelemetry-instrument \
  --service_name vecapi-worker \
  dramatiq app.worker.actors --processes 1 --threads 1 &

wait
