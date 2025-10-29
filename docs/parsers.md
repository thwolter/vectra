# Parsers

Parsers convert uploaded files into structured content that downstream components can embed. They implement the `ParserProtocol` from `app/parsers/protocols.py`, which provides two key methods:

- `parse(file: str) -> ParserResult` — returns LangChain `Document` objects.
- `to_markdown() -> str | None` — produces a Markdown rendition for storage and streaming.

## Provider Registry

`app/parsers/providers.py` registers named factories that construct parser instances. Services request a parser by name, usually sourced from the active processing profile:

```python
from src.parsers.providers import parser_provider
parser = parser_provider(name="llama", config=ParserConfig())
```

The registry ships with these providers:

| Name | Implementation | Highlights |
| --- | --- | --- |
| `docling` | `DoclingParser` | Install extras via `pip install .[docling]`; OCR + Markdown chunks. |
| `llama` | `LlamaParser` | Default parser; integrates with LlamaParse/Llama Cloud (`LLAMA_CLOUD_API_KEY`). |
| `chatdoc` | `ChatDocParser` | Cloud-based fallback for complex PDFs; polls ChatDoc API until extraction completes. |

Provider factories coerce generic `ParserConfig` instances into the concrete configuration class expected by each parser.

## Markdown Normalization

`UploadPipeline.parse_document` expects each `Document` to include:

- `metadata["digest"]` — stable hash of the uploaded file.
- `metadata["source"]` — original filename (used by the document repository and delete paths).

Parsers should ensure these keys are set; the pipeline adds them defensively if missing.

## Switching the Default Parser

- Set `DEFAULT_PARSER` in `.env` to choose between registered providers.
- Profiles can override parser choices and pass provider-specific config (`ProcessingProfileSettings.parser_config`).
- For LlamaParse, export `LLAMA_CLOUD_API_KEY` before starting the worker or API.

Refer to the [Dev Guide](dev_guide.md) for examples of registering alternate providers or toggling defaults via environment variables.

## Extending

To register a new parser:

1. Implement the `ParserProtocol`.
2. Register it with `register_parser_provider("my_parser", lambda config: MyParser(config=config))`.
3. Optionally extend `ParserConfig` to expose parser-specific options.
4. Update the relevant profile to use `parser="my_parser"`.
