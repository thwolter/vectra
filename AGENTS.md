# Repository Guidelines

## Project Structure & Module Organization
The FastAPI service and domain logic live in `app/`, organized by capability (`api/`, `core/`, `services/`, `vector/`, etc.) with `app/main.py` exposing the ASGI entrypoint. Background workers reside in `app/worker/actors`. Database migrations sit in `alembic/`, CLI helpers in `commands/`, and shell automation in `scripts/` (see `scripts/run-dev.sh`). Tests mirror the runtime modules under `tests/unit`, with `tests/integration` and `tests/e2e` reserved for slower suites; shared fixtures and synthetic payloads live in `tests/fixtures` and `tests/data`.

## Build, Test, and Development Commands
- Initial setup: `uv sync` installs runtime and dev dependencies from `pyproject.toml` / `uv.lock`.
- Local API + worker: `scripts/run-dev.sh` launches `uvicorn` and the Dramatiq worker with OpenTelemetry defaults.
- Ad-hoc server: `uv run uvicorn app.main:app --reload --port 8010`.
- Database utilities: `uv run python manage.py db unlock` or `drop-tables` to manage advisory locks and SQLModel tables.

## Coding Style & Naming Conventions
Target Python 3.12 with four-space indentation and 120-character lines (`tool.ruff.line-length`). `ruff fmt` enforces single quotes, while `isort --profile=black` keeps imports ordered. Prefer snake_case for modules, functions, and variables; PascalCase only for SQLModel classes and Pydantic schemas. Run `uv run pre-commit run --all-files` before pushing to apply formatting, import sorting, secret scans, and type checks.

## Testing Guidelines
Unit suites run quickly via `uv run pytest -m "unit"`; the default `uv run pytest` command already skips `integration`, `e2e`, and `slow` markers per `pyproject.toml`. Opt into broader coverage with `uv run pytest -m "integration"` or `uv run pytest -m "e2e"` after provisioning the required services (`POSTGRES_URL`, `AWS_*`, etc.). Store helpers in `tests/support` and name new files `test_<module>.py` to align with `pytest` discovery.

## Commit & Pull Request Guidelines
Commits follow Commitizen conventional commits (`feat(observability): …`, `fix(logging): …`). Use `uv run cz commit` to scaffold messages and keep scopes aligned with top-level packages. Before opening a PR, ensure pre-commit passes, reference the related issue or ticket, and summarize behavior changes and test coverage; attach screenshots or logs when the change affects user-visible APIs or observability dashboards.
