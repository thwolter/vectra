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
dramatiq app.worker.actors
```

The module `app.worker.actors` auto-configures the broker (Redis + monitoring middleware) and exposes the `process_upload` actor.

## Monitoring

Prometheus metrics are exposed from the FastAPI application at `/metrics` when `monitoring_enabled` and `metrics_endpoint_enabled` are `true`. The middleware publishes the following key series:

- `dramatiq_tasks_enqueued_total{actor="process_upload"}` – enqueue rate.
- `dramatiq_tasks_queue_depth{actor="process_upload"}` – approximate in-flight queue depth.
- `dramatiq_tasks_in_progress{actor="process_upload"}` – tasks actively processed by workers.
- `dramatiq_tasks_processed_total{actor="process_upload",status="success|failure"}` – success/failure counters.
- `dramatiq_task_duration_seconds{actor="process_upload"}` – histogram of task execution latency.
- `dramatiq_alerts_total{actor="process_upload",severity="error"}` – alert emission counter.

Scrape `/metrics` with Prometheus and export the resulting dashboards to Grafana as needed.

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
