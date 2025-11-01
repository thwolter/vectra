# Deployment

This guide explains how to deploy VecAPI to container platforms (Coolify, Kubernetes, ECS, etc.) and how to run the web and worker tiers safely in production.

## Build & Publish the Image

The repository ships with a multi-stage Dockerfile that bundles dependencies into a virtualenv and copies the source tree to `/app`. To build a production image:

```bash
docker build -t ghcr.io/finrag/vecapi:<tag> .
docker push ghcr.io/finrag/vecapi:<tag>
```

Key notes:

- `PYTHON_VERSION` (build arg) defaults to 3.12.
- The final image expects configuration via environment variables (see [Configuration](../configuration.md)).
- Entry point: `/app/scripts/entrypoint.sh`.

## Container Configuration

| Variable | Description |
| --- | --- |
| `START_WEB` | Set to `true` to run the FastAPI service (default). |
| `START_WORKER` | Set to `true` to run the Dramatiq worker (default). |
| `DEPLOY_START_BOTH` | Historical flag; use the combination of `START_WEB`/`START_WORKER` instead. |
| `PORT` | Uvicorn port (default `8000`). |
| `UVICORN_RELOAD` | Enable live reload for dev/test (`true`/`false`). |
| `DRAMATIQ_WORKERS`, `DRAMATIQ_THREADS` | Control worker parallelism. |
| `DEPLOY_SKIP_MIGRATIONS` | Skip Alembic auto-run if your platform manages migrations separately. |

### Running Web and Worker Separately

1. **Web service only** (default behaviour):
   - Set `START_WEB=true`, `START_WORKER=false`.
   - Points the container at Postgres, Redis, and S3.
2. **Worker service**:
   - Set `START_WEB=false`, `START_WORKER=true`.
   - Ensure Redis is reachable and share the same environment (Postgres URL, access keys).
3. **Combined (small deployments / Coolify single dyno)**:
   - Leave both flags `true`. The entrypoint spawns Dramatiq in the background and keeps Uvicorn as PID 1.

### Docker Compose Example

```yaml
services:
  web:
    image: ghcr.io/finrag/vecapi:latest
    environment:
      START_WEB: "true"
      START_WORKER: "false"
      POSTGRES_URL: ${POSTGRES_URL}
      REDIS_URL: ${REDIS_URL}
      OPENAI_API_KEY: ${OPENAI_API_KEY}
      AWS__ACCESS_KEY_ID: ${AWS__ACCESS_KEY_ID}
      AWS__SECRET_ACCESS_KEY: ${AWS__SECRET_ACCESS_KEY}
      AWS__S3_BUCKET: ${AWS__S3_BUCKET}
    ports:
      - "8010:8000"
  worker:
    image: ghcr.io/finrag/vecapi:latest
    environment:
      START_WEB: "false"
      START_WORKER: "true"
      POSTGRES_URL: ${POSTGRES_URL}
      REDIS_URL: ${REDIS_URL}
      OPENAI_API_KEY: ${OPENAI_API_KEY}
      AWS__ACCESS_KEY_ID: ${AWS__ACCESS_KEY_ID}
      AWS__SECRET_ACCESS_KEY: ${AWS__SECRET_ACCESS_KEY}
      AWS__S3_BUCKET: ${AWS__S3_BUCKET}
    depends_on:
      - web
```

## Database Migrations

- The entrypoint runs `alembic upgrade head` on boot (with retry logic). Disable by setting `DEPLOY_SKIP_MIGRATIONS=true` and invoking migrations via CI/CD or release tooling.
- For manual control:

```bash
uv run alembic upgrade head
uv run alembic downgrade -1  # rollback one revision
```

- Database connectivity:
  - Ensure the target role enforces row-level security; superuser connections raise `RlsNotEnforcedError`.
  - Configure default schema via `DB_SCHEMA`.

## Secrets & Environment

- Provide sensitive values through your platform’s secret manager (Coolify env vars, Kubernetes secrets, AWS SSM).
- Minimum secrets: `POSTGRES_URL`, `REDIS_URL`, `OPENAI_API_KEY`, and S3 credentials (unless `DOCUMENT_STORE=local`).
- When using LlamaParse: set `LLAMA_CLOUD__API_KEY`.

## Health Checks

- `GET /healthz` — basic readiness (returns `{"status":"ok"}`).
- `GET /readyz` — indicates the application is ready for traffic.
- Dramatiq worker heartbeat keys reside in Redis as `worker:<hostname>:<pid>` when `REDIS_URL` is supplied.

## Scaling Guidelines

- Run at least one dedicated worker container per active environment to avoid blocking uploads due to `START_WEB=true` only deployments.
- Tune `DRAMATIQ_WORKERS` and `DRAMATIQ_THREADS` based on CPU: start with 1×CPU process and 4–8 threads per process.
- PGVector embedding throughput depends on network latency to OpenAI and Postgres; monitor `dramatiq_tasks_queue_depth` to size workers.
- Enable autoscaling triggers on:
  - Queue depth > 50 for >5 minutes.
  - Task duration histogram P95 crossing ingest SLAs.

## Storage Considerations

- S3 paths: `s3://{AWS__S3_BUCKET}/{collection}/{document_uuid}/`.
- To rotate buckets or migrate tenants, update `AWS__S3_BUCKET` and redeploy; URIs regenerate on future ingestions.
- Local filesystem backing (`DOCUMENT_STORE=local`) is suitable only for tests or ephemeral environments.

## Disaster Recovery

- Store Postgres backups (point-in-time or nightly) and S3 versioning to recover lost documents.
- Replay ingestion by re-uploading files; **ingestion versions** (parser/chunker/embedding fingerprints) prevent duplicate embeddings when settings match.
- Monitor `dramatiq_alerts_total` to receive proactive notifications of pipeline failures.
