# Configuration

VecAPI reads configuration from environment variables via `src/core/config.Settings`. Nested models use the `__` delimiter (`LLAMA_CLOUD__API_KEY`, `EMBEDDING__MODEL`, etc.). This page lists the key settings grouped by concern and highlights required secrets.

## Minimum Required Variables

| Variable | Description |
| --- | --- |
| `POSTGRES_URL` | SQLModel + PGVector connection string (e.g. `postgresql://user:pass@host:6432/vectra` via pgBouncer). |
| `REDIS_URL` | Redis broker URL for Dramatiq (e.g. `redis://redis:6379/0`). |
| `OPENAI_API_KEY` | API key for the default embeddings provider. Required unless you override embeddings. |
| `AWS__ACCESS_KEY_ID`, `AWS__SECRET_ACCESS_KEY`, `AWS__REGION`, `AWS__S3_BUCKET` | Credentials for storing artifacts in S3 when `DOCUMENT_STORE=s3`. |

Local development can switch to the filesystem provider with `DOCUMENT_STORE=local`, which removes the AWS dependency.

## Application & Runtime

| Variable | Default | Notes |
| --- | --- | --- |
| `ENV` | `production` | Semantic environment (`development`, `production`, `testing`). Propagates to OTEL resource attributes. |
| `APP_NAME` | `Vectra` | Display name reported via OpenAPI and telemetry. |
| `DEBUG` | `True` | Enables verbose logging and SQLAlchemy echo. |
| `VERSION` | Derived from `pyproject` | Automatically loaded with `load_version()`. |
| `DEFAULT_PROFILE` | `default` | Reserved for future profile registry. |
| `DEFAULT_PARSER` | `llama` | Reserved for the forthcoming parser registry; the current pipeline instantiates `LlamaParser` directly. |

## Database & Tenancy

| Variable | Default | Notes |
| --- | --- | --- |
| `POSTGRES_URL` | **required** | Automatically normalised to `postgresql+asyncpg://` for async sessions. |
| `app_schema` | `vectra` | Sets the Postgres schema used by SQLModel and PGVector search path. |
| `DB_POOL_SIZE` | `20` | Base SQLAlchemy pool size tuned for pgBouncer transaction pooling. |
| `DB_MAX_OVERFLOW` | `20` | Burst capacity beyond the base pool. |
| `DB_POOL_TIMEOUT` | `30` | Seconds to wait for a pooled connection before raising. |
| `CORS_ALLOW_ORIGINS` | `()` | Comma or space separated origins; parsed into a tuple. |

Sessions are wrapped by `tenauth` so tenant metadata is injected into the connection (`app.tenant_id`, search path).

## Storage Backends

| Variable | Default | Notes |
| --- | --- | --- |
| `DOCUMENT_STORE` | `s3` | Switch to `local` for filesystem storage under `LOCAL_FILE_PATH`. |
| `LOCAL_FILE_PATH` | `../documents` | Root directory when using the local store. |
| `AWS__ACCESS_KEY_ID` | **required when `DOCUMENT_STORE=s3`** | IAM credentials for S3. |
| `AWS__SECRET_ACCESS_KEY` | **required** | Secret key for S3. |
| `AWS__REGION` | `eu-west-1` | Region used when building the S3 client. |
| `AWS__S3_BUCKET` | `vecapi-documents` | Bucket name storing originals and Markdown. |
| `AWS__S3_PATH` | `documents` | Prefix for generated keys. |

Both stores place artifacts under `{collection}/{document_uuid}/`.

## Upload Constraints

| Variable | Default | Notes |
| --- | --- | --- |
| `ALLOWED_UPLOAD_FILES__ALLOWED_EXTENSIONS` | `['pdf', 'docx', ...]` | List of supported suffixes. |
| `ALLOWED_UPLOAD_FILES__CONTENT_TYPE` | Common doc MIME types | Mime-type allowlist. |
| `ALLOWED_UPLOAD_FILES__UPLOAD_SIZE_LIMIT` | `104857600` (100 MiB) | Maximum file size. |

Mirror these settings in client applications so uploads are validated before hitting the API.

## Parser Integrations

| Variable | Default | Notes |
| --- | --- | --- |
| `LLAMA_CLOUD__API_KEY` | `None` | Required in production when using the Llama parser. |
| `LLAMA_CLOUD__MODEL` | `openai-gpt-5-mini` | Parsing model identifier. |
| `LLAMA_CLOUD__HIGH_RES_OCR` | `True` | Toggle OCR enhancements. |
| `CHATDOC_API_KEY` | `None` | Enables the ChatDoc fallback parser. |
| `CHATDOC_API_URL` | `https://api.chatdoc.com` | Base URL for ChatDoc polling. |

Install parser extras where needed: `uv sync --extra docling` or provide hosted APIs for Llama/ChatDoc.

## Embeddings & Vector Store

| Variable | Default | Notes |
| --- | --- | --- |
| `EMBEDDING__MODEL` | `text-embedding-3-small` | Model requested from the embeddings provider. |
| `EMBEDDING__DIM` | `1536` | Expected vector dimension; must match the model. |
| `EMBEDDING__MAX_TOKENS_PER_REQUEST` | `300000` | Token budget per batch, enforced by `BatchBuilder`. |
| `EMBEDDING__MAX_DOCS_PER_BATCH` | `100` | Hard cap to prevent exploding batch sizes. |
| `EMBEDDING__COLLECTION` | `default` | Default PGVector collection name used by `UploadService`. |

You can inject a custom `Embeddings` instance via dependency overrides or by implementing a processing profile.

## Dramatiq & Worker Settings

| Variable | Default | Notes |
| --- | --- | --- |
| `DRAMATIQ_BROKER_URL` | **required for asynchronous processing** | Redis URL; fallback to in-process stub when unset. |
| `DRAMATIQ_QUEUE_NAME` | `upload-processing` | Queue served by the `process_upload` actor. |
| `DRAMATIQ_TIME_LIMIT_MS` | `900000` (15 min) | Kills long-running jobs. |
| `DRAMATIQ_MAX_RETRIES` | `3` | Retries before marking failure. |
| `WORKER_HEARTBEAT_TTL` | `30` | Redis TTL (seconds) for liveness keys. |
| `WORKER_HEARTBEAT_INTERVAL` | `10` | Sleep between heartbeats. |

Set `START_WORKER=true` (see deployment guide) when running the worker in a shared container.

## Authentication & JWT

| Variable | Default | Notes |
| --- | --- | --- |
| `JWT_SECRET` | `dev-secret-change-me` | Symmetric key for issuing access tokens (replace in production). |
| `JWT_ISSUER` | `vecapi` | Issuer claim. |
| `JWT_AUDIENCE` | `vecapi-clients` | Audience claim. |
| `JWT_TTL_SECONDS` | `3600` | Default lifetime for issued tokens. |

Auth middleware expects `Authorization: Bearer <token>`; integrate with your identity provider to mint compatible tokens.

## Logging & Observability

| Variable | Default | Notes |
| --- | --- | --- |
| `LOG_LEVEL` | `WARNING` | Loguru level for console output. |
| `LOG_CONSOLE_PLAIN` | `True` | Keep console logs human-readable. |
| `LOG_ENQUEUE` | `True` | Offload logging to background thread. |
| `LOG_BACKTRACE` | `True` | Include tracebacks in logs. |
| `LOG_DIAGNOSE` | `False` | Disable Loguru diagnose mode by default. |
| `LOG_REMOVE_DEFAULT_SINK` | `True` | Avoid duplicate handlers when Uvicorn configures logging. |
| `MONITORING_ENABLED` | `True` | Global toggle for metrics/alerts. |
| `METRICS_ENDPOINT_ENABLED` | `True` | Reserved for potential Prometheus exporters. |
| `OTEL_ENABLED` | `True` | Enables OpenTelemetry instrumentation. |
| `OTEL_LOGS_EXPORTER` | `otlp` | Set to `none` to disable OTLP log export. |
| `LOG_OTEL_JSON` | `True` | Use JSON when shipping logs via OTLP. |
| `SERVICE_NAMESPACE` | `finrag` | OpenTelemetry resource attribute. |
| `SERVICE_NAME_APP` | `src` | Reported service name for the API process. |
| `SERVICE_NAME_WORKER` | `worker` | Reported service name for Dramatiq. |
| `DEPLOYMENT_ENV` | `development` | Additional OTEL attribute. |
| `ALERTING_WEBHOOK_URL` | `None` | When set, Dramatiq failures POST JSON payloads to the URL. |

Export OTLP telemetry by providing `OTEL_EXPORTER_OTLP_ENDPOINT`, `OTEL_EXPORTER_OTLP_HEADERS`, and other standard variables.

## Derived Helpers

- `settings.async_postgres_url` rewrites the DSN for `asyncpg` usage (`postgresql+asyncpg://`).
- `settings.cors_allow_origins` parses comma/space separated strings and deduplicates origins.
- `AllowedUploadFiles`, `LlamaCloudSettings`, `EmbeddingSettings`, etc., can be overridden wholesale by providing nested JSON via environment variables (e.g. `EMBEDDING='{"model":"text-embedding-3-large"}'`).

Reload the FastAPI app or worker after changing environment variables; settings are cached via `functools.lru_cache`.
