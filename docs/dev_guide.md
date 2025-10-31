# Development Workflow

This guide covers local setup, coding standards, testing, and tips for working on VecAPI’s ingestion pipeline.

## Environment Setup

1. Install prerequisites:
   - Python 3.12
   - libpq / PostgreSQL client libraries
   - Redis (optional but required for realistic worker tests)
2. Create and populate `.env` (see [Configuration](configuration.md) for required variables).
3. Install dependencies with [`uv`](https://github.com/astral-sh/uv):

   ```bash
   uv sync
   ```

4. Launch the API and worker locally:

   ```bash
   scripts/run-dev.sh
   ```

   The script starts Uvicorn (`uvicorn src.main:app`) and a single Dramatiq worker with OpenTelemetry instrumentation.

5. Visit `http://localhost:8010/docs` for interactive Swagger docs.

## Coding Standards

- Python 3.12, four-space indentation, 120-character lines (`tool.ruff.line-length`).
- Format with `ruff fmt`, lint with `ruff check`, sort imports using `isort --profile=black`.
- Commit using Commitizen scopes (`uv run cz commit`).
- Before opening a PR:

  ```bash
  uv run pre-commit run --all-files
  ```

## Testing

- Unit tests: `uv run pytest -m "unit"`
- Full suite (excludes `integration`, `e2e`, `slow` markers by default): `uv run pytest`
- Opt into broader coverage:

  ```bash
  uv run pytest -m "integration"
  uv run pytest -m "e2e"
  ```

Provide required env vars (`POSTGRES_URL`, `AWS_*`, `OPENAI_API_KEY`) when running integration/e2e suites.

## Debugging Tips

- Use `scripts/run-dev.sh` with `LOG_LEVEL=DEBUG` and `UVICORN_RELOAD=true` for rapid iteration.
- Dramatiq worker emits Redis heartbeat keys (`worker:<hostname>:<pid>`) when `REDIS_URL` is configured.
- Replay a payload inline during debugging:

  ```python
  import asyncio
  from services.factory import get_upload_service
  from schemas.upload import ContinueProcessingInput

  payload = ContinueProcessingInput(...)
  asyncio.run(get_upload_service().continue_processing(payload=payload))
  ```

- Traces are exported automatically when `OTEL_EXPORTER_OTLP_ENDPOINT` is set; follow spans `process_upload_message` and `store_markdown` to inspect timing.

## Customising the Pipeline

- `UploadPipeline.parse_document` currently instantiates `LlamaParser`. Swap implementations by subclassing `UploadPipeline` or by injecting a different parser in `services.factory.get_upload_service`.
- Adjust storage providers by setting `DOCUMENT_STORE` (`s3` vs `local`) or by implementing the `StoreProtocol`.
- To experiment with embeddings, override `vector.factory.get_vectorstore` via dependency injection or monkeypatching in tests.

## Style Conventions

- Use type hints throughout; the project targets `mypy`-compatible code even though `mypy` is not enforced yet.
- When adding modules, prefer colocating them under `src/<capability>/` (mirroring runtime responsibilities).
- Write concise docstrings and targeted comments for complex logic; avoid restating obvious assignments.

## Tooling Shortcuts

- `uv run uvicorn src.main:app --reload --port 8010` — manual API launch.
- `uv run dramatiq src.worker.actors --processes 1 --threads 4` — additional worker process.
- `uv run alembic revision --autogenerate -m "feat: new table"` — create migrations (review before applying).

## Troubleshooting Checklist

- **DB connection errors** — confirm `POSTGRES_URL` uses `postgresql://` (lowercase `postgres://` is normalised automatically).
- **RLS enforcement** — avoid superuser roles; API throws `RlsNotEnforcedError` on misconfiguration.
- **Parser failures** — ensure `LLAMA_CLOUD__API_KEY` is set and `llama-parse` dependency is installed.
- **Embeddings timeouts** — reduce `DRAMATIQ_THREADS` or upgrade your provider quota.

Refer to the [Runbooks](operations/runbooks.md) for operational incidents and escalation paths.
