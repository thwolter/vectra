from __future__ import annotations

from pathlib import Path
from typing import Any, List, Protocol

from langchain_core.documents import Document
from loguru import logger

from core.config import get_settings


class LoaderProtocol(Protocol):
    async def aload(self) -> List[Document]: ...


class LoaderFactory(Protocol):
    def __call__(self, file: str) -> LoaderProtocol: ...


class LlamaParser:
    def __init__(
        self,
        *,
        loader: LoaderProtocol | LoaderFactory | None = None,
    ):
        self._parsed_docs: List[Document] | None = None
        self.settings = get_settings()

        if loader:
            self.loader = loader
        else:
            # Lazy import and wrap the sync LlamaParse loader with an async interface
            def _factory(file: str) -> LoaderProtocol:
                try:
                    from llama_parse import LlamaParse  # type: ignore
                except Exception as e:  # pragma: no cover - only hit when optional dep missing
                    raise ImportError('llama-parse is not installed. Install with `pip install llama-parse`') from e

                settings = self.settings
                if self.settings.llama_cloud.api_key:
                    api_key = self.settings.llama_cloud.api_key.get_secret_value()
                else:
                    raise ValueError('LLAMA_CLOUD__API_KEY required for LlamaParser')

                parser = LlamaParse(
                    api_key=api_key,
                    parse_mode=settings.llama_cloud.parse_mode,
                    model=settings.llama_cloud.model,
                    high_res_ocr=settings.llama_cloud.high_res_ocr,
                    adaptive_long_table=settings.llama_cloud.adaptive_long_table,
                    outlined_table_extraction=settings.llama_cloud.outlined_table_extraction,
                    output_tables_as_HTML=settings.llama_cloud.output_tables_as_HTML,
                    extract_layout=settings.llama_cloud.extract_layout,
                    continuous_mode=settings.llama_cloud.continuous_mode,
                )

                class _AsyncLoader:
                    def __init__(self, _parser: Any, _file: str):
                        self._parser = _parser
                        self._file = _file

                    async def aload(self) -> List[Document]:
                        import asyncio

                        logger.debug('LlamaParse: loading data from %s', self._file)

                        def _load_sync() -> List[Document]:
                            # llama-parse returns a result object; convert its markdown documents
                            # into LangChain Documents so the rest of the pipeline can stay generic.
                            result = self._parser.parse(self._file)
                            try:
                                nodes = result.get_markdown_documents() or []
                            except AttributeError as exc:  # pragma: no cover - defensive guard
                                raise AttributeError('LlamaParse result missing get_markdown_documents()') from exc

                            docs: List[Document] = []
                            for i, node in enumerate(nodes):
                                content = (
                                    getattr(node, 'text', None)
                                    or getattr(node, 'page_content', None)
                                    or getattr(node, 'markdown', None)
                                )
                                if content is None:
                                    content = str(node)
                                metadata = dict(getattr(node, 'metadata', {}) or {})
                                metadata.update({'parser': 'LlamaParser', 'node_index': i})
                                docs.append(Document(page_content=content or '', metadata=metadata))
                            return docs

                        return await asyncio.to_thread(_load_sync)

                return _AsyncLoader(parser, file)

            self.loader = _factory

    async def parse(self, file: str) -> List[Document]:
        if not Path(file).exists():
            raise ValueError(f'File not found: {file}')

        try:
            logger.debug('Parsing document with LlamaParser...')
            loader = self.loader(file) if callable(self.loader) else self.loader
            docs = await loader.aload()
            logger.success(f'Parsed {len(docs)} documents.')

            if docs:
                for doc in docs:
                    # Ensure parser metadata is set in case custom loader omitted it
                    doc.metadata.update({'parser': 'LlamaParser'})

            self._parsed_docs = docs
            return docs

        except Exception as e:  # pragma: no cover - error path
            logger.error(f'Error during LlamaParser parsing: {e}')
            raise

    async def to_markdown(self) -> str:
        if not self._parsed_docs:
            raise ValueError('No documents parsed yet. Call parse() first.')
        return '\n\n'.join(doc.page_content for doc in self._parsed_docs if doc.page_content)
