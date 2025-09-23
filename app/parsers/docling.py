from functools import partial
from pathlib import Path
from typing import List, Protocol

import tiktoken
from docling_core.transforms.chunker.hybrid_chunker import HybridChunker
from docling_core.transforms.chunker.tokenizer.openai import OpenAITokenizer
from langchain_core.documents import Document
from langchain_docling import DoclingLoader
from loguru import logger

from .schemas import ParserConfig, ParseResult


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
