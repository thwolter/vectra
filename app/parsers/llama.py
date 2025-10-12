from __future__ import annotations

from functools import partial
from pathlib import Path
from typing import List, Protocol, Any

from langchain_core.documents import Document
from loguru import logger

from app.core.config import get_settings
from .schemas import ParserConfig, ParseResult


class LlamaParserConfig(ParserConfig):
    """Configuration for LlamaParser.

    Attributes
    ----------
    result_type: str
        Output format produced by LlamaParse. Common values: 'markdown', 'text'.
    use_ocr: bool
        Whether to enable OCR for scanned PDFs.
    """

    result_type: str = 'markdown'
    use_ocr: bool = True


class LoaderProtocol(Protocol):
    async def aload(self) -> List[Document]: ...


class LoaderFactory(Protocol):
    def __call__(self, file: str) -> LoaderProtocol: ...


class LlamaParser:
    def __init__(
        self,
        *,
        config: LlamaParserConfig,
        loader: LoaderProtocol | LoaderFactory | None = None,
    ):
        self.config = config
        self._parsed_docs: List[Document] | None = None

        if loader:
            self.loader = loader
        else:
            # Lazy import and wrap the sync LlamaParse loader with an async interface
            def _factory(file: str) -> LoaderProtocol:
                try:
                    from llama_parse import LlamaParse  # type: ignore
                except Exception as e:  # pragma: no cover - only hit when optional dep missing
                    raise ImportError(
                        'llama-parse is not installed. Install with `pip install llama-parse`'
                    ) from e

                settings = get_settings()
                api_key = (
                    settings.llama_cloud_api_key.get_secret_value()
                    if settings.llama_cloud_api_key
                    else None
                )

                parser = LlamaParse(
                    api_key=api_key,
                    result_type=self.config.result_type,
                    use_ocr=self.config.use_ocr,
                )

                class _AsyncLoader:
                    def __init__(self, _parser: Any, _file: str):
                        self._parser = _parser
                        self._file = _file

                    async def aload(self) -> List[Document]:
                        import asyncio

                        logger.debug('LlamaParse: loading data from %s', self._file)

                        def _load_sync() -> List[Document]:
                            # llama-parse returns a list of "Document" objects (LlamaIndex),
                            # we normalize to langchain Documents.
                            nodes = self._parser.load_data(self._file)
                            docs: List[Document] = []
                            for i, n in enumerate(nodes):
                                content = getattr(n, 'text', None) or getattr(n, 'page_content', '')
                                metadata = dict(getattr(n, 'metadata', {}) or {})
                                metadata.update({'parser': 'LlamaParser', 'node_index': i})
                                docs.append(Document(page_content=content or '', metadata=metadata))
                            return docs

                        return await asyncio.to_thread(_load_sync)

                return _AsyncLoader(parser, file)

            self.loader = _factory

    async def parse(self, file: str) -> ParseResult:
        if not Path(file).exists():
            raise ValueError(f'File not found: {file}')

        try:
            logger.debug('Parsing document with LlamaParser...')
            loader = self.loader(file) if callable(self.loader) else self.loader
            docs = await loader.aload()
            logger.success(f'Parsed {len(docs)} document chunks.')

            if docs:
                for doc in docs:
                    # Ensure parser metadata is set in case custom loader omitted it
                    doc.metadata.update({'parser': 'LlamaParser'})

            self._parsed_docs = docs
            return ParseResult(documents=docs)

        except Exception as e:  # pragma: no cover - error path
            logger.error(f'Error during LlamaParser parsing: {e}')
            raise

    async def to_markdown(self) -> str:
        if not self._parsed_docs:
            raise ValueError('No documents parsed yet. Call parse() first.')
        return '\n\n'.join(doc.page_content for doc in self._parsed_docs if doc.page_content)
