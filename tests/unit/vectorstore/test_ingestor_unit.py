from unittest.mock import create_autospec, Mock, AsyncMock

import pytest
from langchain_core.documents import Document

from app.repositories import Ingestion
from app.schemas.enums import CollectionEnum
from app.vector.ingestor import DocumentIngestor


@pytest.fixture
def ingestor():
    # Note: DocumentIngestor uses Ingestion classmethods directly; this repo mock is unused
    repo = create_autospec(Ingestion, instance=True)
    repo.upsert = AsyncMock(return_value=None)
    repo.exists = AsyncMock(return_value=False)

    ingestor = DocumentIngestor(CollectionEnum.DEFAULT.value)
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
    # Patch Ingestion class used inside DocumentIngestor
    FakeIngestion = create_autospec(Ingestion, spec_set=True)
    FakeIngestion.exists = AsyncMock(return_value=False)
    FakeIngestion.create = AsyncMock(return_value=None)
    monkeypatch.setattr('app.vector.ingestor.Ingestion', FakeIngestion)

    # Provide a fake vectorstore instance and make factory return it
    vstore = Mock()
    vstore.add_documents = Mock(return_value=None)
    vstore.collection_name = 'default'

    def fake_get_vectorstore(*args, **kwargs):
        return vstore

    monkeypatch.setattr('app.vector.ingestor.get_vectorstore', fake_get_vectorstore)

    docs = [Document(page_content='Hello World')]

    result = await ingestor.ingest(mock_session, docs=docs, digest=random_digest)
    assert result is not None
    assert vstore.add_documents.call_count == 1
