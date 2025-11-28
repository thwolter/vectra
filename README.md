# VecAPI — Vectra Ingestion Service

![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white)
![Ruff](https://img.shields.io/badge/Ruff-linted-FCC21B?logo=ruff&logoColor=black)
![isort](https://img.shields.io/badge/isort-imports-blue?logo=python&logoColor=white)
![Commitizen](https://img.shields.io/badge/Commitizen-conventional-orange?logo=git&logoColor=white)
![Gitleaks](https://img.shields.io/badge/Gitleaks-secrets%20safe-critical?logo=git-lfs&logoColor=white)

VecAPI is the ingestion and vectorization backend that powers Financials_RAG. The FastAPI service accepts customer documents, tracks parser/chunker/embedding fingerprints to deduplicate them, pushes heavy processing to Dramatiq workers, and writes enriched chunks into Postgres + PGVector so downstream Retrieval-Augmented Generation (RAG) agents can search trusted content.

## Highlights

- Idempotent ingestion with binary hashing and resumable job lifecycle management.
- Multi-tenant aware session, storage, and vector abstractions backed by SQLModel and PGVector.
- Extensible parsing layer with first-class support for LlamaParse and optional Docling extras.
- Separation of concerns between synchronous API handlers and asynchronous Dramatiq workers.
- Observability baked in via OpenTelemetry tracing, metrics exporters, and structured Loguru logging.

## Architecture At A Glance

The service receives uploads on `/v1/uploads`, stores the originals, normalizes text, generates embeddings, and serves artifacts and job status back to callers. A worker tier drains Redis-backed Dramatiq queues to execute long-running tasks (parsing, chunking, embedding). Postgres with PGVector persists document metadata and embeddings, while object storage (S3 or filesystem) holds the raw and normalized assets.

Refer to `docs/index.md` and the deeper dives (`docs/architecture.md`, `docs/vector.md`, `docs/ingestion.md`) for sequence diagrams, data contracts, and operational runbooks.

## Getting Started

### Prerequisites

- Python 3.12+
- [uv](https://github.com/astral-sh/uv) for dependency and virtualenv management
- Running infrastructure: Postgres (with PGVector extension), Redis, and object storage (S3 or compatible)

### Installation

```bash
uv sync
cp .env.example .env  # populate credentials, connection strings, and feature toggles
```

> Tip: `DEFAULT_PARSER` controls which parser profile is loaded. Provide `LLAMA_CLOUD_API_KEY` for LlamaParse, or install Docling support with `uv sync --extra docling`.

### Database Migrations

```bash
uv run alembic upgrade head
```

Alembic manages schema revisions. See `docs/operations/runbooks.md` for rollback procedures.

### Run The Stack

```bash
scripts/run-dev.sh        # starts uvicorn + Dramatiq with OpenTelemetry defaults
```

The script launches the FastAPI app (`src.main:app` on port `8010` by default) and a single-threaded worker. You can run them independently:

```bash
uv run uvicorn src.main:app --reload --port 8010
uv run dramatiq src.worker.actors --processes 1 --threads 1
```

Use the `/healthz` and `/readyz` endpoints to confirm service status.

### Vector Store Performance

- `langchain_pg_embedding` is now partitioned by `tenant_id` (with a default catch-all) and ships with a cosine HNSW index on `embedding vector(1536)`; run `uv run alembic upgrade head` to apply the migrations.
- A pgBouncer sidecar (transaction pooling on port `6432`) fronts Postgres; `POSTGRES_URL` now targets pgBouncer while Alembic continues to point at the primary instance.
- Database pooling is tuned for pgBouncer (`DB_POOL_SIZE`, `DB_MAX_OVERFLOW`, `DB_POOL_TIMEOUT`) and prepared-statement caches are disabled to keep transaction pooling safe.

## Testing & Quality Gates

- Unit tests: `uv run pytest -m "unit"`
- Full suite (skips marked `integration`, `e2e`, `slow` by default): `uv run pytest`
- Static checks & formatting: `uv run pre-commit run --all-files`

Enable local Git hooks once with:

```bash
uv run pre-commit install
```

The configured hooks enforce Ruff linting/formatting, isort ordering, gitleaks secret scanning, Pyrefly type checks, and Commitizen branch policy. Craft commit messages through Commitizen with `uv run cz commit`.

## Project Structure

- `src/main.py` — FastAPI entrypoint, CORS, logging, OpenTelemetry bootstrap.
- `src/api/v1/` — Upload, job, document, and streaming routes.
- `src/services/` — Intake orchestration, job lifecycle, chunking, and embedding workflows.
- `src/repositories/` — SQLModel repositories and PGVector data access.
- `src/store/` — Pluggable object store implementations (S3 and filesystem).
- `src/worker/` — Dramatiq broker configuration and actors.
- `alembic/` — Schema migrations.
- `docs/` — MkDocs documentation site.
- `tests/` — Unit fixtures and suites mirroring runtime modules.

## Documentation

Launch the MkDocs site locally with:

```bash
uv run mkdocs serve
```

The documentation stack includes API walkthroughs, parser guides, observability setup, and operational runbooks.

## Contributing

1. Branch from `main` and keep changes focused.
2. Run `uv run pre-commit run --all-files` and the appropriate pytest markers.
3. Use `uv run cz commit` for conventional commit messages.
4. Include context in PR descriptions (behavioral changes, tests run, linked issues).

For environment variables, deployment toggles, and runbooks, consult `docs/configuration.md` and `docs/operations/`.
