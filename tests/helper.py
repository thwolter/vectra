from __future__ import annotations

import io
import pickle
from pathlib import Path

from langchain_core.documents import Document
from loguru import logger
from starlette.testclient import TestClient

from app.main import app
from app.parsers.protocols import ParserProtocol
from app.parsers.schemas import ParseResult
from app.schemas.enums import CollectionEnum
from app.services.dependencies import get_upload_service as _get_upload_service_dep
from app.services.upload_service import UploadService
from app.store.local_store import LocalFileStore
from app.store.protocols import StoreProtocol

from typing import Any, cast


def make_files_param(apple_report_first_page):
    pdf = apple_report_first_page
    assert pdf.exists(), f'Test PDF not found at {pdf}'
    with open(pdf, 'rb') as f:
        files = {'file': (pdf.name, io.BytesIO(f.read()), 'application/pdf')}
    return files


class TestClientWithCleanup(TestClient):
    """TestClient subclass that carries a typed cleanup attribute.

    Tests can set `client._cleanup = callable` without mypy/pyright errors.
    """

    _cleanup: callable  # type: ignore[assignment]

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)


def make_client_financial(base_path: Path) -> TestClientWithCleanup:
    def _financial_upload_service_override(tmp_path):
        store = LocalFileStore(base_path=tmp_path, collection=CollectionEnum.FINANCIAL)
        return UploadService(
            collection=CollectionEnum.FINANCIAL,
            store=cast(StoreProtocol, store),
        )

    def _finalizer():
        app.dependency_overrides.pop(_get_upload_service_dep, None)

    app.dependency_overrides[_get_upload_service_dep] = (
        lambda: _financial_upload_service_override(base_path)
    )
    client = TestClientWithCleanup(app)
    client._cleanup = _finalizer  # attach for manual cleanup
    return client


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
            raise ValueError(
                f'Unsupported sample_docs format in {self.sample_path}: {type(data)}'
            )

        if not isinstance(docs, list):
            raise ValueError(
                "sample_docs.pkl must contain list[Document] or a dict with 'documents'"
            )

        self._docs = docs
        self._markdown = markdown

    async def parse(self) -> ParseResult:
        logger.debug('Fake parsing document...')
        self._load_once()
        return ParseResult(documents=list(self._docs or []))

    async def to_markdown(self) -> str:
        logger.debug('Fake markdown conversion...')
        self._load_once()
        return self._markdown or 'test markdown'
