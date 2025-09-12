from unittest.mock import create_autospec, Mock, AsyncMock

import pytest
from langchain_core.documents import Document
from langchain_postgres import PGVector

from app.repositories.ingestion_repository import Ingestion
from app.schemas.enums import CollectionEnum
from app.vector.ingestor import DocumentIngestor


@pytest.fixture
def ingestor():
    repo = create_autospec(Ingestion, instance=True)
    repo.create = AsyncMock(return_value=None)
    repo.exists = AsyncMock(return_value=False)

    ingestor = DocumentIngestor(CollectionEnum.DEFAULT)
    ingestor._ingestion_repo = repo
    return ingestor


@pytest.mark.asyncio
async def test_ingest_empty_docs_returns_none(ingestor, random_digest, mock_session):
    docs = []
    result = await ingestor.ingest(mock_session, docs=docs, digest=random_digest)
    assert result is not None
    assert result.skipped is True
    assert result.total_docs == 0
    assert result.reason == 'no_documents'


@pytest.mark.asyncio
async def test_ingest_calls_add_documents(
    ingestor, random_digest, mock_session, monkeypatch
):
    # Patch the repository used inside DocumentIngestor to avoid real DB calls
    FakeIngestion = create_autospec(Ingestion, instance=False, spec_set=True)
    # The ingestor checks embeddings via classmethod exists_by_digest
    FakeIngestion.exists = AsyncMock(return_value=False)
    # Marking ingestion uses insert_key
    FakeIngestion.create = AsyncMock(return_value=None)
    monkeypatch.setattr('app.vector.ingestor.Ingestion', FakeIngestion)

    vstore = create_autospec(PGVector, instance=True)
    vstore.add_documents = Mock(return_value=None)
    vstore.collection_name = 'default'

    ingestor.vectorstore = vstore

    docs = [Document(page_content='Hello World')]

    result = await ingestor.ingest(mock_session, docs=docs, digest=random_digest)
    assert result is not None
    assert vstore.add_documents.call_count == 1
