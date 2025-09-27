#!/usr/bin/env bash
set -euo pipefail

# Simple entrypoint allowing this container to run:
# - the FastAPI web server (uvicorn)
# - the Dramatiq worker
# - or both (worker in background, web in foreground)
#
# Configure via environment variables:
#   START_WEB=true|false        (default: true)
#   START_WORKER=true|false     (default: false)
#   START_BOTH=true|false       (default: false)
#   UVICORN_WORKERS             (default: 2)
#   PORT                        (default: 8000)
#   DRAMATIQ_WORKERS            (default: 1)
#   DRAMATIQ_THREADS            (default: 8)
#   DRAMATIQ_QUEUE_NAME         (optional; falls back to settings)
#
# In Coolify you can:
# - Run two services from the same image: one with START_WEB=true (default), another with START_WORKER=true
# - Or run a single service with START_BOTH=true

START_WEB=${START_WEB:-true}
START_WORKER=${START_WORKER:-false}
START_BOTH=${START_BOTH:-false}
UVICORN_WORKERS=${UVICORN_WORKERS:-2}
PORT=${PORT:-8000}
DRAMATIQ_WORKERS=${DRAMATIQ_WORKERS:-1}
DRAMATIQ_THREADS=${DRAMATIQ_THREADS:-8}

start_web() {
  echo "[entrypoint] Starting uvicorn (workers=${UVICORN_WORKERS}, port=${PORT})"
  exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT}" --workers "${UVICORN_WORKERS}"
}

start_worker() {
  echo "[entrypoint] Starting Dramatiq worker (processes=${DRAMATIQ_WORKERS}, threads=${DRAMATIQ_THREADS})"
  # Note: dramatiq takes --processes and --threads to control concurrency.
  # The target module must import and register actors and the broker.
  exec dramatiq app.worker.actors --processes "${DRAMATIQ_WORKERS}" --threads "${DRAMATIQ_THREADS}"
}

start_both() {
  echo "[entrypoint] Starting BOTH: web and worker"
  # Start worker in background, then start web in foreground. Use trap to forward signals.
  dramatiq app.worker.actors --processes "${DRAMATIQ_WORKERS}" --threads "${DRAMATIQ_THREADS}" &
  WORKER_PID=$!
  echo "[entrypoint] Dramatiq worker PID=${WORKER_PID}"

  # Forward termination signals to child processes
  trap 'echo "[entrypoint] Received SIGTERM, stopping..."; kill -TERM ${WORKER_PID} 2>/dev/null || true; wait ${WORKER_PID} 2>/dev/null || true; exit 0' TERM INT

  # Run web in foreground (PID 1)
  uvicorn app.main:app --host 0.0.0.0 --port "${PORT}" --workers "${UVICORN_WORKERS}"
}

if [[ "${START_BOTH}" == "true" ]]; then
  start_both
elif [[ "${START_WORKER}" == "true" ]]; then
  start_worker
elif [[ "${START_WEB}" == "true" ]]; then
  start_web
else
  echo "[entrypoint] Nothing to start. Set START_WEB=true or START_WORKER=true or START_BOTH=true"
  exit 1
fi
