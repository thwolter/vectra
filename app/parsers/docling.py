from pathlib import Path
from typing import List

import tiktoken
from docling_core.transforms.chunker.hybrid_chunker import HybridChunker
from docling_core.transforms.chunker.tokenizer.openai import OpenAITokenizer
from langchain_core.documents import Document
from langchain_docling import DoclingLoader
from langchain_docling.loader import ExportType
from loguru import logger

from .protocols import ParserProtocol
from .schemas import ParserConfig, ParseResult


class DoclingParserConfig(ParserConfig):
    """Configuration for DoclingParser."""

    pass


class DoclingParser(ParserProtocol):
    def __init__(
        self,
        file: str,
        *,
        config: DoclingParserConfig | None = None,
        loader: DoclingLoader | None = None,
    ):
        """
        Initialize the DoclingParser.

        :param file: Path to the document file
        :param config: Optional configuration dictionary with keys:
            - model_name: Name of the tokenizer model (default: "gpt-4")
            - max_tokens: Maximum tokens for the tokenizer (default: 128*1024)
            - header_chunks: Number of chunks to use for header extraction (default: 3)
        """

        if not Path(file).exists():
            raise ValueError(f'File not found: {file}')

        self.config = config or DoclingParserConfig()
        self.file = file

        self.tokenizer = OpenAITokenizer(
            tokenizer=tiktoken.encoding_for_model(self.config.model_name),
            max_tokens=self.config.max_tokens,  # context window length for OpenAI models
        )

        self.loader = loader or DoclingLoader(
            file_path=file,
            export_type=ExportType.DOC_CHUNKS,
            chunker=HybridChunker(tokenizer=self.tokenizer),
        )

        self._parsed_docs: List[Document] | None = None

    async def parse(self) -> ParseResult:
        """
        Parse the document asynchronously.

        :return: List of Document objects
        """
        try:
            logger.debug('Parsing document with DoclingLoader...')
            docs = await self.loader.aload()
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
