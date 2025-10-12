# Developer guide

This guide explains how to configure and run the ingestion pipeline components relevant to parsers.

## Set the default parser

To use the Llama parser (Llama Cloud / LlamaParse) as the default parser:

1. Ensure you have a Llama Cloud API key available as an environment variable. In your `.env` file:

   ```bash
   LLAMA_CLOUD_API_KEY=llx-...your-key...
   ```

2. The application reads this via settings as `settings.llama_cloud_api_key`. No additional wiring is needed.

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
   parser = parser_provider(name="llama", config=LlamaParserConfig(result_type="markdown", use_ocr=True))
   ```

4. To make Llama the default across the app, set a profile or configuration in your composition root where the parser provider is selected (e.g., service factory). If your project exposes an environment toggle, use it to choose `llama`. If not, replace `"docling"` with `"llama"` in the parser selection code.

!!! warning
    Always set `LLAMA_CLOUD_API_KEY` before running ingestion when using the Llama parser, otherwise parsing will fail at runtime.

## Notes

- Llama parser normalizes outputs to LangChain `Document` objects and adds `metadata.parser = "LlamaParser"` for traceability.
- Docling remains available and can be selected with `name="docling"`.
