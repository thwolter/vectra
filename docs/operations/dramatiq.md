# Dramatiq Worker Operations

This document outlines how to run the Dramatiq worker stack, configure Redis, and consume the new observability endpoints.

## Configuration

Set the following environment variables alongside the existing application configuration:

| Variable | Description |
| --- | --- |
| `DRAMATIQ_BROKER_URL` | Redis connection string (e.g. `redis://redis:6379/0`). Leaving this unset executes jobs inline during API requests (useful for tests). |
| `DRAMATIQ_QUEUE_NAME` | Optional override for the upload processing queue (defaults to `upload-processing`). |
| `DRAMATIQ_TIME_LIMIT_MS` | Maximum execution time per task in milliseconds (defaults to 15 minutes). |
| `DRAMATIQ_MAX_RETRIES` | Maximum retry attempts before the job is marked failed (defaults to 3). |
| `ALERTING_WEBHOOK_URL` | Optional HTTP endpoint that will receive JSON payloads whenever a task fails. |

Redis must be reachable from both the API and worker containers. Provision Redis via your preferred infrastructure provider and expose it through `DRAMATIQ_BROKER_URL`.

## Running Workers

Use the stock `dramatiq` CLI to run workers once the environment variables are set:

```bash
DRAMATIQ_BROKER_URL=redis://redis:6379/0 \
DRAMATIQ_QUEUE_NAME=upload-processing \
uv run dramatiq src.worker.actors
```

The module `src.worker.actors` configures the broker (Redis + monitoring middleware) and exposes the `process_upload` actor.

## Monitoring

OpenTelemetry metrics are emitted via OTLP and should be collected by an OpenTelemetry Collector. No Prometheus `/metrics` endpoint is exposed by the API. The middleware publishes the following key series (names unchanged):

- `dramatiq_tasks_enqueued_total{actor="process_upload"}` – enqueue rate.
- `dramatiq_tasks_queue_depth{actor="process_upload"}` – approximate in-flight queue depth.
- `dramatiq_tasks_in_progress{actor="process_upload"}` – tasks actively processed by workers.
- `dramatiq_tasks_processed_total{actor="process_upload",status="success|failure"}` – success/failure counters.
- `dramatiq_task_duration_seconds{actor="process_upload"}` – histogram of task execution latency.
- `dramatiq_alerts_total{actor="process_upload",severity="error"}` – alert emission counter.

To run locally without a backend, set `OTEL_EXPORTER_OTLP_ENDPOINT` to your Collector (e.g., `http://localhost:4318`) and use `scripts/run-dev.sh`, which starts both the API and worker with `opentelemetry-instrument`.


## Alerting

When `ALERTING_WEBHOOK_URL` is configured, every task failure triggers an HTTP POST with the following schema:

```json
{
  "timestamp": "2024-12-11T12:34:56.000000+00:00",
  "actor": "process_upload",
  "message_id": "...",
  "payload": {"payload": "..."},
  "exception": "Traceback(...)"
}
```

Use this hook to integrate with Slack, PagerDuty, or any other incident channel. Failures are also logged via Loguru for local diagnosis.


## Coolify deployment notes

You can run the web API and the worker using the same image in different service definitions, or run both in a single container:

- Web only (default): `START_WEB=true`, `START_WORKER=false`.
- Worker only: `START_WEB=false`, `START_WORKER=true`.
- Both in one container: leave both `true`; the entrypoint forks the worker before starting Uvicorn.

Optional tuning:
- `DRAMATIQ_WORKERS` (processes, default 1)
- `DRAMATIQ_THREADS` (threads per process, default 8)
- `UVICORN_WORKERS` (default 2)

Ensure `DRAMATIQ_BROKER_URL` points to your Redis instance and is shared by both services.
