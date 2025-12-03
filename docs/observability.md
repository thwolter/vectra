# Observability Overview

VecAPI instruments logs, metrics, and traces with OpenTelemetry so operators can diagnose ingestion issues quickly. This page summarises what each signal covers and how to wire exporters in different environments.

## Logging

- Logging is configured centrally via `nexor.logging.configure_loguru_logging`. It:
  - Removes Loguru’s default sink to prevent duplicate messages when Uvicorn configures logging.
  - Adds a human-readable console sink (stderr) honouring `LOG_LEVEL`, `LOG_ENQUEUE`, `LOG_BACKTRACE`, and `LOG_DIAGNOSE`.
  - Optionally bridges Loguru into Python’s stdlib logging when `OTEL_LOGS_EXPORTER != 'none'`, enabling OTLP log export.
- Service-specific binds (`component='src'` / `'worker'`) ensure structured metadata in JSON log streams.
- Adjust logging at runtime by setting `LOG_LEVEL=INFO` or overriding sink flags via environment variables.

## Distributed Tracing

- `nexor.observability.init_otel_fastapi` installs a global `TracerProvider` and instruments FastAPI handlers when the app boots.
- `nexor.observability.init_otel_worker` initialises the worker with instrumentation helpers. Dramatiq actors manually create spans (`prepare_payload`, `process_upload_message`) for each job.
- Spans include resource attributes set by environment variables: `SERVICE_NAME_APP`, `SERVICE_NAME_WORKER`, `SERVICE_NAMESPACE`, and `DEPLOYMENT_ENV`.
- When exporting to Grafana Cloud, Honeycomb, Tempo, or another OTLP receiver, provide `OTEL_EXPORTER_OTLP_ENDPOINT` and `OTEL_EXPORTER_OTLP_HEADERS="Authorization=Bearer <token>"`.

### Key Span Names

| Span | Emitted by | Notes |
| --- | --- | --- |
| `HTTP POST /v1/uploads` | FastAPI auto instrumentation | Includes request/response attributes and route parameters. |
| `src.startup` | FastAPI lifespan hook | Marks application boot and logs version/namespace metadata. |
| `prepare_payload` | Dramatiq worker | JSON rehydration for `ContinueProcessingInput`. |
| `process_upload_message` | Dramatiq worker | Wraps the full upload pipeline execution. |

Use these spans to correlate client uploads with downstream ingestion jobs and vector writes.

## Metrics

- `src/monitoring/middleware.DramatiqMonitoringMiddleware` emits OTLP metrics for queue depth, in-progress tasks, and durations.
- Instruments live under the `monitoring.metrics` module and share stable metric names:

| Metric | Type | Dimensions | Description |
| --- | --- | --- | --- |
| `dramatiq_tasks_enqueued_total` | Counter | `actor` | Task enqueue rate per actor. |
| `dramatiq_tasks_queue_depth` | UpDownCounter | `actor` | Approximate queue backlog. |
| `dramatiq_tasks_in_progress` | UpDownCounter | `actor` | Actors currently executing. |
| `dramatiq_tasks_processed_total` | Counter | `actor`, `status` | Success/failure counts. |
| `dramatiq_task_duration_seconds` | Histogram | `actor` | Execution latency distribution (seconds). |
| `dramatiq_alerts_total` | Counter | `actor`, `severity` | Alert events emitted by the worker. |

- Configure exporters via standard OTEL environment variables (`OTEL_METRIC_EXPORT_INTERVAL`, `OTEL_EXPORTER_OTLP_PROTOCOL`, etc.). Metrics are pushed via `PeriodicExportingMetricReader` every 60 seconds by default.

## Alerting

- The `AlertManager` (`src/monitoring/alerting.py`) sends JSON payloads to `ALERTING_WEBHOOK_URL` when an actor fails after retries. Integrate with Slack or PagerDuty by pointing the webhook to your automation layer.
- Payloads include the actor name, message id, payload kwargs, and exception repr. Failures increment `dramatiq_alerts_total`.

## Dashboards & Suggested Queries

| Signal | Suggested View | Purpose |
| --- | --- | --- |
| Logs | Filter `component` (`src`, `worker`) and `job_id` | Investigate ingestion failures or duplicates. |
| Traces | Trace search on `process_upload_message` | Follow an individual job from enqueue to completion. |
| Metrics | Queue depth vs. processed rate | Capacity planning; detect saturation before SLAs are hit. |

## Local Verification

1. Start the stack with `scripts/run-dev.sh`.
2. Export an OTLP collector endpoint, e.g. `OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318`.
3. Upload a file through `/v1/uploads`.
4. Inspect traces/metrics via your collector UI or `docker logs` if you are running the OpenTelemetry Collector locally.

If you do not want telemetry during tests, set `OTEL_ENABLED=false` or `MONITORING_ENABLED=false`; both the API and worker respect these toggles.
