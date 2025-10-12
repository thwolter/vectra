# Developer Guide

This guide covers the development workflow for VecAPI: environment setup, code style, testing, and parser configuration.

## Environment Setup

!!! note
    Database URL whitespace: Environment variables are trimmed defensively in the app and Alembic. If a DB URL accidentally has trailing spaces (e.g., ends with "/test "), connections may fail with errors like `database "test " does not exist`. Ensure there are no stray spaces in `.env`.

1. Install system dependencies (Python 3.12, libpq, Redis if running workers locally).
2. Sync the project environment:

   ```bash
   uv sync
   ```

3. Copy `.env.example` to `.env` and populate secrets such as database URLs, Redis, AWS credentials, and parser API keys.
4. Start the local stack:

   ```bash
   scripts/run-dev.sh
   ```

   The script launches both `uvicorn app.main:app --reload` and the Dramatiq worker with OpenTelemetry wiring.

## Coding Standards

- Format code with `ruff fmt` and sort imports via `isort --profile=black` (enforced by pre-commit).
- Target 120-character line length, four-space indentation, and snake_case naming for functions/modules.
- Run the full suite of hooks before pushing:

  ```bash
  uv run pre-commit run --all-files
  ```

## Testing

- Unit tests: `uv run pytest -m "unit"`
- Full suite: `uv run pytest`
- Markers `integration`, `e2e`, and `slow` remain opt-in; provision external services (Postgres, AWS) before running them.

## Debugging Workers

- Dramatiq workers log heartbeats to Redis when `REDIS_URL` is set; check keys `worker:<hostname>:<pid>`.
- OpenTelemetry traces emitted by the worker use the service name `vecapi-worker`.
- To replay an upload payload locally, serialize a `ContinueProcessingInput` and call `UploadService.continue_processing`.

## Parser Configuration

To use the Llama parser (Llama Cloud / LlamaParse) as the default parser:

1. Add the API key to `.env`:

   ```bash
   LLAMA_CLOUD_API_KEY=llx-...your-key...
   ```

2. The application reads this via `settings.llama_cloud_api_key`. No additional wiring is needed.

3. Choose the parser provider by name wherever a parser is requested via the providers registry. The built-in providers are:
   - `docling` (default)
   - `llama`

   Example (Python):

   ```python
   from app.parsers.providers import parser_provider
   from app.parsers.schemas import ParserConfig

   parser = parser_provider(name="llama", config=ParserConfig())
   # or to use custom options for Llama:
   from app.parsers.llama import LlamaParserConfig
   parser = parser_provider(name="llama", config=LlamaParserConfig(result_type="markdown"))
   ```

4. To make Llama the default across the app, update the processing profile or override the environment variable below.

!!! warning
    Always set `LLAMA_CLOUD_API_KEY` before running ingestion when using the Llama parser, otherwise parsing will fail at runtime.

## Switch Parser via Environment

To switch the default parser globally without code changes, set the environment variable in your `.env`:

```bash
# Use Docling (default)
DEFAULT_PARSER=docling

# Or switch to Llama
DEFAULT_PARSER=llama
```

The profile registry reads `DEFAULT_PARSER` at startup to register the in-process default profile accordingly. You can still override the parser per-profile by setting the `parser` field in a custom profile configuration.
