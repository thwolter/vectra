#!/usr/bin/env bash

set -euo pipefail

START_WEB=${START_WEB:-false}
START_WORKER=${START_WORKER:-false}
start_both=${start_both:-true}
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
    if /opt/venv/bin/alembic -c alembic.ini upgrade head; then
      echo "[entrypoint] Migrations applied successfully"
      break
    else
      if (( attempt >= max_retries )); then
        echo "[entrypoint] Failed to apply migrations after ${attempt} attempts"
        break
        exit 1
      fi
      echo "[entrypoint] Migration attempt ${attempt} failed; retrying in ${delay}s..."
      sleep ${delay}
      attempt=$(( attempt + 1 ))
    fi
  done
}

start_web() {
  echo "[entrypoint] Starting uvicorn (single worker, port=${PORT})"
  exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT}"
}

start_worker() {
  echo "[entrypoint] Starting Dramatiq worker (processes=${DRAMATIQ_WORKERS}, threads=${DRAMATIQ_THREADS})"
  exec dramatiq app.worker.actors --processes "${DRAMATIQ_WORKERS}" --threads "${DRAMATIQ_THREADS}"
}

start_both() {
  echo "[entrypoint] Starting BOTH: web and worker"
  dramatiq app.worker.actors --processes "${DRAMATIQ_WORKERS}" --threads "${DRAMATIQ_THREADS}" &
  WORKER_PID=$!
  echo "[entrypoint] Dramatiq worker PID=${WORKER_PID}"

  # Forward termination signals to child processes
  trap 'echo "[entrypoint] Received SIGTERM, stopping..."; kill -TERM ${WORKER_PID} 2>/dev/null || true; wait ${WORKER_PID} 2>/dev/null || true; exit 0' TERM INT

  # Run web in foreground (PID 1)
  exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT}"
}

run_migrations

if [[ "$START_WEB" == "true" && "$START_WORKER" == "true" ]]; then
  start_both
elif [[ "${START_WORKER}" == "true" ]]; then
  start_worker
elif [[ "${START_WEB}" == "true" ]]; then
  start_web
else
  echo "[entrypoint] Nothing to start. Set START_WEB=true or START_WORKER=true."
  exit 1
fi
