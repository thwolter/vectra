# Developer guide

## Setup

- Python 3.12
- Install: `pip install -e .[dev]`
- Env vars: `OPENAI_API_KEY`, `POSTGRES_URL`, S3 credentials

## Run

- API: `uvicorn app.main:app --reload`
- Docs: `mkdocs serve`

## Test

- Run `pytest -q` (CI: ruff, pyright --strict, pytest)

## Conventions

- Async-first; use relative imports (`from core.config import settings`).
- Compute `binary_hash` before any storage.
- Store both original and markdown to S3.
