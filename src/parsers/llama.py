from __future__ import annotations

import re
from pathlib import Path
from typing import Any, List, Protocol

from langchain_core.documents import Document
from loguru import logger

from core.config import get_settings

from .schemas import ParserConfig, ParseResult


class LlamaParserConfig(ParserConfig):
    """Configuration for LlamaParser.

    Attributes
    ----------
    result_type: str
        Output format produced by LlamaParse. Common values: 'markdown', 'text'.
    use_ocr: bool
        Whether to enable OCR for scanned PDFs.
    heading_chunking_enabled: bool
        If True, split markdown output into semantic chunks by section headings.
    min_heading_level: int
        Minimum markdown heading level to split on (e.g., 2 splits on '##' and deeper).
    """

    result_type: str = 'markdown'
    use_ocr: bool = True
    heading_chunking_enabled: bool = True
    min_heading_level: int = 2


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
                    raise ImportError('llama-parse is not installed. Install with `pip install llama-parse`') from e

                settings = get_settings()
                api_key = settings.llama_cloud_api_key.get_secret_value() if settings.llama_cloud_api_key else None

                parser = LlamaParse(
                    api_key=api_key,
                    parse_mode='parse_page_with_agent',  # The parsing mode
                    model='openai-gpt-5-mini',  # The model to use
                    high_res_ocr=True,  # Whether to use high resolution OCR (slower but more precise)
                    adaptive_long_table=True,
                    # Adaptive long table. LlamaParse will try to detect long table and adapt the output
                    outlined_table_extraction=True,  # Whether to try to extract outlined tables
                    output_tables_as_HTML=True,  # Whether to output tables as HTML in the markdown output
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

    @staticmethod
    def _split_markdown_by_headings(text: str, min_level: int = 2) -> list[tuple[int, str, str]]:
        """Split markdown text into sections by headings.

        Returns a list of tuples: (heading_level, heading_title, section_text)
        where section_text includes the heading line followed by its content until
        the next heading of same or higher level.
        """
        if not text:
            return []

        # Find all headings
        pattern = re.compile(r'^(#{1,6})[ \t]+(.+)$', re.MULTILINE)
        # Only split on the specified heading level (e.g., H2) so deeper subsections stay within their parent
        matches = [m for m in pattern.finditer(text) if len(m.group(1)) == min_level]
        if not matches:
            return []

        sections: list[tuple[int, str, str]] = []
        for idx, m in enumerate(matches):
            level = len(m.group(1))
            title = m.group(2).strip()
            start = m.start()
            end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
            section_text = text[start:end].rstrip()
            sections.append((level, title, section_text))
        return sections

    def _chunk_documents_by_headings(self, docs: List[Document]) -> List[Document]:
        new_docs: List[Document] = []
        section_count = 0
        for doc in docs:
            text = doc.page_content or ''
            parts = self._split_markdown_by_headings(text, self.config.min_heading_level)
            if not parts:
                new_docs.append(doc)
                continue
            for i, (level, title, content) in enumerate(parts):
                md = dict(doc.metadata)
                md.update(
                    {
                        'parser': 'LlamaParser',
                        'section_index': section_count,
                        'section_title': title,
                        'section_level': level,
                    }
                )
                new_docs.append(Document(page_content=content, metadata=md))
                section_count += 1
        return new_docs

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

            # Apply semantic chunking by headings for markdown outputs
            if self.config.heading_chunking_enabled and self.config.result_type.lower() == 'markdown':
                try:
                    chunked = self._chunk_documents_by_headings(docs)
                    if len(chunked) != len(docs):
                        logger.debug(
                            'LlamaParser: heading chunking split %d -> %d chunks',
                            len(docs),
                            len(chunked),
                        )
                    docs = chunked
                except Exception as e:
                    logger.warning(f'LlamaParser: heading chunking skipped due to error: {e}')

            self._parsed_docs = docs
            return ParseResult(documents=docs)

        except Exception as e:  # pragma: no cover - error path
            logger.error(f'Error during LlamaParser parsing: {e}')
            raise

    async def to_markdown(self) -> str:
        if not self._parsed_docs:
            raise ValueError('No documents parsed yet. Call parse() first.')
        return '\n\n'.join(doc.page_content for doc in self._parsed_docs if doc.page_content)
