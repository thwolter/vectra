from __future__ import annotations

from functools import partial
from pathlib import Path
from typing import Any, List, Protocol, TypedDict, TYPE_CHECKING

from langchain_core.documents import Document
from loguru import logger

from .schemas import ParserConfig, ParseResult

if TYPE_CHECKING:
    from langchain_docling import DoclingLoader


class _DoclingRuntime(TypedDict):
    tiktoken: Any
    HybridChunker: Any
    OpenAITokenizer: Any
    DoclingLoader: type


_runtime_cache: _DoclingRuntime | None = None


def _load_docling_runtime() -> _DoclingRuntime:
    """Import docling dependencies lazily so the module can exist without extras installed."""
    global _runtime_cache  # noqa: WPS420
    if _runtime_cache is not None:
        return _runtime_cache

    try:
        import tiktoken  # noqa: WPS433
        from docling_core.transforms.chunker.hybrid_chunker import HybridChunker  # noqa: WPS433
        from docling_core.transforms.chunker.tokenizer.openai import OpenAITokenizer  # noqa: WPS433
        from langchain_docling import DoclingLoader  # noqa: WPS433
    except ImportError as exc:  # pragma: no cover - exercised when optional deps missing
        raise ImportError(
            'Docling parser extras are not installed. Install with "uv add .[docling]"'
            ' or "pip install vectra[docling]".',
        ) from exc

    _runtime_cache = _DoclingRuntime(
        tiktoken=tiktoken,
        HybridChunker=HybridChunker,
        OpenAITokenizer=OpenAITokenizer,
        DoclingLoader=DoclingLoader,
    )
    return _runtime_cache


class DoclingParserConfig(ParserConfig):
    """Configuration for DoclingParser."""

    pass


class LoaderFactory(Protocol):
    def __call__(self, file: str) -> DoclingLoader: ...


class DoclingParser:
    def __init__(
        self,
        *,
        config: DoclingParserConfig,
        loader: DoclingLoader | LoaderFactory | None = None,
    ):
        self.config = config
        runtime = _load_docling_runtime()
        OpenAITokenizer = runtime['OpenAITokenizer']
        DoclingLoader = runtime['DoclingLoader']
        HybridChunker = runtime['HybridChunker']
        tiktoken = runtime['tiktoken']

        self.tokenizer = OpenAITokenizer(
            tokenizer=tiktoken.encoding_for_model(self.config.model_name),
            max_tokens=self.config.max_tokens,  # context window length for OpenAI models
        )
        if loader:
            self.loader = loader
        else:
            self.loader = partial(DoclingLoader, chunker=HybridChunker(tokenizer=self.tokenizer))

        self._parsed_docs: List[Document] | None = None

    async def parse(self, file: str) -> ParseResult:
        if not Path(file).exists():
            raise ValueError(f'File not found: {file}')

        try:
            logger.debug('Parsing document with DoclingLoader...')
            loader = self.loader(file) if callable(self.loader) else self.loader
            docs = await loader.aload()
            logger.success(f'Parsed {len(docs)} document chunks.')

            if docs:
                for doc in docs:
                    doc.metadata.update({'parser': 'DoclingParser'})

            # Cache the result
            self._parsed_docs = docs
            return ParseResult(documents=docs)

        except Exception as e:
            logger.error(f'Import error during parsing: {e}')
            raise

    async def to_markdown(self) -> str:
        """
        Convert parsed documents to markdown format.

        :return: Markdown representation of the documents
        """
        if not self._parsed_docs:
            raise ValueError('No documents parsed yet. Call parse() first.')

        # Join document contents with newlines
        return '\n\n'.join(doc.page_content for doc in self._parsed_docs if doc.page_content)
