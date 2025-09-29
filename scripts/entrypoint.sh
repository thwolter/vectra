#!/usr/bin/env bash

set -euo pipefail

# --- OpenTelemetry defaults (configurable via env) ---
OTEL_ENABLED=${OTEL_ENABLED:-true}
export OTEL_SERVICE_NAME=${OTEL_SERVICE_NAME:-vecapi}
export OTEL_PYTHON_LOGGING_AUTO_INSTRUMENTATION_ENABLED=${OTEL_PYTHON_LOGGING_AUTO_INSTRUMENTATION_ENABLED:-true}
export OTEL_TRACES_EXPORTER=${OTEL_TRACES_EXPORTER:-otlp}
export OTEL_METRICS_EXPORTER=${OTEL_METRICS_EXPORTER:-otlp}
export OTEL_LOGS_EXPORTER=${OTEL_LOGS_EXPORTER:-otlp}
export OTEL_EXPORTER_OTLP_ENDPOINT=${OTEL_EXPORTER_OTLP_ENDPOINT:-https://otlp-gateway-prod-us-west-0.grafana.net/otlp}
# -----------------------------------------------------

# Simple entrypoint allowing this container to run:
# - the FastAPI web server (uvicorn)
# - the Dramatiq worker
# - or both (worker in background, web in foreground)
#
# Configure via environment variables:
#   START_WEB=true|false        (default: true)
#   START_WORKER=true|false     (default: false)
#   DEPLOY_START_BOTH=true|false       (default: false)
#   UVICORN_WORKERS             (default: 2)
#   PORT                        (default: 8000)
#   DRAMATIQ_WORKERS            (default: 1)
#   DRAMATIQ_THREADS            (default: 8)
#   DRAMATIQ_QUEUE_NAME         (optional; falls back to settings)
#   DEPLOY_SKIP_MIGRATIONS=true|false  (default: false)
#
# In Coolify you can:
# - Run two services from the same image: one with START_WEB=true (default), another with START_WORKER=true
# - Or run a single service with DEPLOY_START_BOTH=true

START_WEB=${START_WEB:-true}
START_WORKER=${START_WORKER:-false}
DEPLOY_START_BOTH=${DEPLOY_START_BOTH:-false}
UVICORN_WORKERS=${UVICORN_WORKERS:-2}
PORT=${PORT:-8000}
DRAMATIQ_WORKERS=${DRAMATIQ_WORKERS:-1}
DRAMATIQ_THREADS=${DRAMATIQ_THREADS:-8}
DEPLOY_SKIP_MIGRATIONS=${DEPLOY_SKIP_MIGRATIONS:-false}

run_migrations() {
  if [[ "${DEPLOY_SKIP_MIGRATIONS}" == "true" ]]; then
    echo "[entrypoint] DEPLOY_SKIP_MIGRATIONS=true — skipping alembic upgrade"
    return 0
  fi

  echo "[entrypoint] Running database migrations (alembic upgrade head)"
  local max_retries=10
  local attempt=1
  local delay=3
  while true; do
    if alembic -c alembic.ini upgrade head; then
      echo "[entrypoint] Migrations applied successfully"
      break
    else
      if (( attempt >= max_retries )); then
        echo "[entrypoint] Failed to apply migrations after ${attempt} attempts"
        exit 1
      fi
      echo "[entrypoint] Migration attempt ${attempt} failed; retrying in ${delay}s..."
      sleep ${delay}
      attempt=$(( attempt + 1 ))
    fi
  done
}

start_web() {
  run_migrations
  echo "[entrypoint] Starting uvicorn (workers=${UVICORN_WORKERS}, port=${PORT})"
  if [[ "${OTEL_ENABLED}" == "true" ]]; then
    exec opentelemetry-instrument uvicorn app.main:app --host 0.0.0.0 --port "${PORT}" --workers "${UVICORN_WORKERS}"
  else
    exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT}" --workers "${UVICORN_WORKERS}"
  fi
}

start_worker() {
  run_migrations
  echo "[entrypoint] Starting Dramatiq worker (processes=${DRAMATIQ_WORKERS}, threads=${DRAMATIQ_THREADS})"
  # Note: dramatiq takes --processes and --threads to control concurrency.
  # The target module must import and register actors and the broker.
  if [[ "${OTEL_ENABLED}" == "true" ]]; then
    exec opentelemetry-instrument dramatiq app.worker.actors --processes "${DRAMATIQ_WORKERS}" --threads "${DRAMATIQ_THREADS}"
  else
    exec dramatiq app.worker.actors --processes "${DRAMATIQ_WORKERS}" --threads "${DRAMATIQ_THREADS}"
  fi
}

DEPLOY_START_BOTH() {
  run_migrations
  echo "[entrypoint] Starting BOTH: web and worker"
  # Start worker in background, then start web in foreground. Use trap to forward signals.
  if [[ "${OTEL_ENABLED}" == "true" ]]; then
    opentelemetry-instrument dramatiq app.worker.actors --processes "${DRAMATIQ_WORKERS}" --threads "${DRAMATIQ_THREADS}" &
  else
    dramatiq app.worker.actors --processes "${DRAMATIQ_WORKERS}" --threads "${DRAMATIQ_THREADS}" &
  fi
  WORKER_PID=$!
  echo "[entrypoint] Dramatiq worker PID=${WORKER_PID}"

  # Forward termination signals to child processes
  trap 'echo "[entrypoint] Received SIGTERM, stopping..."; kill -TERM ${WORKER_PID} 2>/dev/null || true; wait ${WORKER_PID} 2>/dev/null || true; exit 0' TERM INT

  # Run web in foreground (PID 1)
  if [[ "${OTEL_ENABLED}" == "true" ]]; then
    exec opentelemetry-instrument uvicorn app.main:app --host 0.0.0.0 --port "${PORT}" --workers "${UVICORN_WORKERS}"
  else
    exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT}" --workers "${UVICORN_WORKERS}"
  fi
}

if [[ "${DEPLOY_START_BOTH}" == "true" ]]; then
  DEPLOY_START_BOTH
elif [[ "${START_WORKER}" == "true" ]]; then
  start_worker
elif [[ "${START_WEB}" == "true" ]]; then
  start_web
else
  echo "[entrypoint] Nothing to start. Set START_WEB=true or START_WORKER=true or DEPLOY_START_BOTH=true"
  exit 1
fi
