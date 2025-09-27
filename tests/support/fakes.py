from __future__ import annotations

import pickle
from pathlib import Path

from langchain_core.documents import Document
from loguru import logger

from app.parsers.protocols import ParserProtocol
from app.parsers.schemas import ParseResult


class FakeSampleParser(ParserProtocol):
    """
    Test-only parser that returns LangChain Documents loaded from a pickle file.

    The pickle may contain either:
      - list[Document]
      - dict with keys: {"documents": list[Document], "markdown": str (optional)}
    """

    def __init__(self, sample_path: Path) -> None:
        self.sample_path = Path(sample_path)
        self._docs: list[Document] | None = None
        self._markdown: str | None = None

    def _load_once(self) -> None:
        if self._docs is not None:
            return
        with self.sample_path.open('rb') as f:
            data = pickle.load(f)

        docs: list[Document]
        markdown = ''
        if isinstance(data, list):
            docs = data
        elif isinstance(data, dict):
            docs = data.get('documents') or data.get('docs') or []
            markdown = data.get('markdown') or data.get('md') or ''
        else:
            raise ValueError(f'Unsupported sample_docs format in {self.sample_path}: {type(data)}')

        if not isinstance(docs, list):
            raise ValueError("sample_docs.pkl must contain list[Document] or a dict with 'documents'")

        self._docs = docs
        self._markdown = markdown

    async def parse(self, file: str) -> ParseResult:
        logger.debug('Fake parsing document...')
        self._load_once()
        return ParseResult(documents=list(self._docs or []))

    async def to_markdown(self) -> str:
        logger.debug('Fake markdown conversion...')
        self._load_once()
        return self._markdown or 'test markdown'
