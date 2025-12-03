# OpenTelemetry Integration

VecAPI emits traces, metrics, and logs via the OpenTelemetry (OTEL) SDK. This guide describes how instrumentation is wired, how to configure exporters, and how to validate telemetry locally and in production.

## Instrumentation Overview

| Process | Entry point | Instrumentation |
| --- | --- | --- |
| FastAPI service | `src/main.py` | `init_otel_fastapi()` sets a `TracerProvider`/`MeterProvider`, instruments FastAPI, and bridges Loguru logs. |
| Dramatiq worker | `src/worker/actors.py` | Calls `init_otel_worker()` and wraps each job in spans (`prepare_payload`, `process_upload_message`). |
| Metrics | `src/monitoring/middleware.py` | Custom Dramatiq middleware updates counters/histograms defined in `monitoring.metrics`. |
| Logs | `nexor.logging.configure_loguru_logging()` | Optional OTLP log export via `OTEL_LOGS_EXPORTER`. |

Instrumentation is opt-in: set `OTEL_ENABLED=false` or `MONITORING_ENABLED=false` to disable it entirely (useful for tests).

## Exporter Configuration

All exporters honour standard OTEL environment variables. Common settings:

| Variable | Example | Purpose |
| --- | --- | --- |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | `https://tempo.example.com:443` | Base URL for OTLP/gRPC or OTLP/HTTP exporters. |
| `OTEL_EXPORTER_OTLP_HEADERS` | `Authorization=Bearer <token>` | Authentication header (Grafana Cloud tokens, Honeycomb keys, etc.). |
| `OTEL_EXPORTER_OTLP_PROTOCOL` | `http/protobuf` | Override when your collector expects gRPC (`grpc`). |
| `OTEL_METRIC_EXPORT_INTERVAL` | `30000` | Adjust metric export frequency (milliseconds). |
| `OTEL_RESOURCE_ATTRIBUTES` | `service.version=0.3.0,team=search` | Additional attributes appended to spans/metrics/logs. |

By default, the SDK uses OTLP/HTTP with protobuf encoding and pulls credentials from `OTEL_EXPORTER_OTLP_HEADERS`.

## Local Smoke Test

1. Run an OpenTelemetry Collector locally (or use Grafana Agent). Minimal config:

   ```yaml
   receivers:
     otlp:
       protocols:
         http:
   exporters:
     logging:
       loglevel: debug
   service:
     pipelines:
       traces:
         receivers: [otlp]
         exporters: [logging]
       metrics:
         receivers: [otlp]
         exporters: [logging]
       logs:
         receivers: [otlp]
         exporters: [logging]
   ```

2. Start VecAPI with OTEL endpoint variables:

   ```bash
   export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318
   export OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf
   scripts/run-dev.sh
   ```

3. Upload a file via `/v1/uploads`.
4. Check collector logs for spans named `HTTP POST /v1/uploads` and `process_upload_message`. Metrics (`dramatiq_*`) should appear within ~60 seconds.

## Production Example (Grafana Cloud)

```bash
OTEL_EXPORTER_OTLP_ENDPOINT=https://otlp-gateway-us-east-0.grafana.net/otlp
OTEL_EXPORTER_OTLP_HEADERS="Authorization=Bearer <api-key>"
SERVICE_NAMESPACE=finrag
SERVICE_NAME_APP=vecapi
SERVICE_NAME_WORKER=vecapi-worker
DEPLOYMENT_ENV=production
```

Set these environment variables on both the web and worker services. Grafana Cloud automatically groups spans, metrics, and logs using the resource attributes.

## Logs via OTLP

- Enable by keeping `OTEL_LOGS_EXPORTER=otlp` (default). Set to `none` to disable.
- Logs retain Loguru formatting for the console but forward JSON payloads to the OTLP pipeline.
- Extra attributes (`component`, `job_id`, etc.) appear as structured fields in the log record.

## Metrics Reference

See [Observability](observability.md) for a full list. Key dashboards typically chart:

- `dramatiq_tasks_queue_depth` vs `dramatiq_tasks_processed_total`
- `dramatiq_task_duration_seconds` percentiles
- `dramatiq_alerts_total` (should remain near zero)

## Troubleshooting

| Symptom | Resolution |
| --- | --- |
| No traces exported | Confirm `OTEL_ENABLED=true` and `OTEL_EXPORTER_OTLP_ENDPOINT` is reachable. Check container network policies. |
| Duplicate spans | Ensure auto-instrumentation (`opentelemetry-instrument`) is not wrapping the app; `init_otel_fastapi` already registers instrumentation. |
| Metrics missing dimensions | Metrics add an `actor` attribute; verify collectors are not dropping attributes due to high cardinality filters. |
| OTLP 415/404 errors | Switch `OTEL_EXPORTER_OTLP_PROTOCOL` to `http/protobuf` (Grafana) or `grpc` (Tempo gRPC endpoint). |
| Collector rejects logs | Set `OTEL_LOGS_EXPORTER=none` until the collector supports OTLP logs. |

## Extending Instrumentation

- Wrap additional code with manual spans using `get_tracer(__name__)`.
- Emit custom metrics via `metrics.get_meter(__name__)` with counters or histograms.
- For Dramatiq message context propagation, add middleware that starts spans per message or forwards trace headers when enqueuing.

OpenTelemetry is fully optional during tests; simply export `OTEL_ENABLED=false` to avoid wiring the SDK in pytest.
