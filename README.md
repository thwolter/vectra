# VecAPI — Backend

This repository implements the ingestion and vectorization backend for Financials_RAG.

## Docling optional install

The Docling parser (OCR + vision stack) now lives behind an optional dependency group so the base install stays lightweight. Install it only when needed:

- `uv sync --extra docling` (during local setup), or
- `pip install .[docling]` / `uv add .[docling]` when adding to an existing environment.

Once installed you can select the `"docling"` parser via profiles or `DEFAULT_PARSER`.

## Set Llama parser as default

To use the Llama parser (Llama Cloud / LlamaParse) as the default parser, follow these steps:

1. Add your API key to `.env`:

   ```bash
   LLAMA_CLOUD_API_KEY=llx-...your-key...
   ```

2. Wherever the parser provider is selected (service factory/profile), choose the `llama` provider name instead of `docling`.

   Example (Python):

   ```python
   from app.parsers.providers import parser_provider
   from app.parsers.schemas import ParserConfig

   parser = parser_provider(name="llama", config=ParserConfig())
   ```

   Or use Llama-specific options:

   ```python
   from app.parsers.llama import LlamaParserConfig
   parser = parser_provider(name="llama", config=LlamaParserConfig(result_type="markdown"))
   ```

3. Profiles: If your deployment relies on processing profiles, set the profile's `parser` field to `"llama"` (see `app/profiles/registry.py`). The upload pipeline will then instantiate the Llama parser by default.

Notes:
- The default parser is now Llama. Set `DEFAULT_PARSER=docling` in your `.env` (and install the docling extras) to opt into the Docling pipeline. The profile registry reads this at startup when registering the default profile.
- The app reads `LLAMA_CLOUD_API_KEY` via `settings.llama_cloud_api_key`.
- The Llama parser normalizes outputs to LangChain `Document` objects and sets `metadata["parser"] = "LlamaParser"`.

## Database access & RLS

The API enforces row-level security (RLS) during startup. If you connect with a superuser (or any role that has `rolsuper`/`rolbypassrls`), the application aborts with `RlsNotEnforcedError`.
