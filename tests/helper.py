from __future__ import annotations

import io
import pickle
import uuid
from pathlib import Path

from langchain_core.documents import Document
from loguru import logger
from starlette.testclient import TestClient

from app.core.config import get_settings
from app.main import app
from app.parsers.protocols import ParserProtocol
from app.parsers.schemas import ParseResult
from app.schemas.enums import CollectionEnum
from app.services.factory import get_upload_service as _get_upload_service_dep
from app.services.upload_service import UploadService
from app.store.local_store import LocalFileStore
from app.store.protocols import StoreProtocol

import hashlib
import numpy as np
from typing import List, Tuple, Any, cast

from langchain_core.embeddings import Embeddings
from langchain_postgres import PGVector

from app.vector.ingestor import DocumentIngestor

# Imports for job test arrangement helpers
from app.services.job_service import JobService
from app.repositories.factory import get_job_repository
from app.schemas.jobs import InitJob
from app.metadata.schemas import ProposedMetadata


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


# Deterministic, fast, no network calls
class DeterministicFakeEmbeddings(Embeddings):
    def __init__(self, dim: int = 1536) -> None:
        self.dim = dim

    def _vec_for(self, text: str) -> list[float]:
        # Stable seed per text
        seed = int(hashlib.sha256(text.encode('utf-8')).hexdigest()[:16], 16) % (2**32)
        rng = np.random.default_rng(seed)
        # Draw from N(0,1) then L2-normalize for dot/cosine stability
        v = rng.standard_normal(self.dim)
        v /= np.linalg.norm(v) + 1e-12
        return v.astype(np.float32).tolist()

    def embed_documents(
        self, texts: List[str]
    ) -> List[List[float]]:  # sync OK for tests
        return [self._vec_for(t) for t in texts]

    def embed_query(self, text: str) -> List[float]:
        return self._vec_for(text)


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


def build_test_upload_service(*, collection, base_prefix, sample_docs_path=None):
    if sample_docs_path is None:
        sample_docs_path = Path(__file__).parents[0] / 'data' / 'sample_docs.pkl'

    settings = get_settings()
    embedding = DeterministicFakeEmbeddings(dim=1536)
    fake_vs = PGVector(
        connection=settings.pg_vector_url.get_secret_value(),
        collection_name=collection.value,
        embeddings=embedding,
    )
    fake_ingestor = DocumentIngestor(collection=collection, vectorstore=fake_vs)
    return UploadService(
        collection=collection,
        store=cast(StoreProtocol, LocalFileStore(collection, base_path=base_prefix)),
        ingestor=fake_ingestor,
        parser=FakeSampleParser(sample_docs_path),
    )


# -------------------------------
# Integration test arrangement helpers for job routes
# -------------------------------
async def arrange_job_with_metadata(
    *,
    company: str,
    financial_year: int,
    document_type: str,
    digest: str,
    original_filename: str,
    content_type: str = 'application/pdf',
    size_bytes: int = 1024,
    collection: str = 'default',
) -> Tuple[uuid.UUID, Any]:
    """Create a job row in the database with proposed metadata.

    Returns a tuple of (job_id, job_repository).
    """
    job_service = JobService()
    job_repo = get_job_repository()
    job_id = uuid.uuid4()
    document_id = uuid.uuid4()

    proposed = ProposedMetadata(
        metadata={
            'company': company,
            'financial_year': financial_year,
            'document_type': document_type,
        },
        confidence={},
        conflicts=[],
    )

    init = InitJob(
        job_id=job_id,
        document_uuid=document_id,
        collection=collection,
        digest=digest,
        original_filename=original_filename,
        content_type=content_type,
        size_bytes=size_bytes,
        proposed_metadata=proposed,
    )
    await job_service.init_job(init)
    return job_id, job_repo


def make_api_client() -> TestClient:
    """Return a FastAPI TestClient bound to the app.

    Separated to keep test arrangement concise and uniform.
    """
    return TestClient(app)
