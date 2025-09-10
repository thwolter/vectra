from unittest.mock import create_autospec, Mock, AsyncMock

import pytest
from langchain_core.documents import Document
from langchain_postgres import PGVector

from app.repositories.ingestion_repository import IngestionVersions
from app.schemas.enums import CollectionEnum
from app.vector.ingestor import DocumentIngestor


@pytest.fixture
def ingestor():
    repo = create_autospec(IngestionVersions, instance=True)
    repo.insert_Key = AsyncMock(return_value=None)
    repo.exists_by_digest = AsyncMock(return_value=False)

    ingestor = DocumentIngestor(CollectionEnum.DEFAULT)
    ingestor._ingestion_repo = repo
    return ingestor


@pytest.mark.asyncio
async def test_ingest_empty_docs_returns_none(ingestor, digest_str):
    docs = []
    result = await ingestor.ingest(docs=docs, digest=digest_str)
    assert result is not None
    assert result.skipped is True
    assert result.total_docs == 0
    assert result.reason == 'no_documents'


@pytest.mark.asyncio
async def test_ingest_calls_add_documents(ingestor, digest_str):
    vstore = create_autospec(PGVector, instance=True)
    vstore.add_documents = Mock(return_value=None)
    vstore.collection_name = 'default'

    ingestor.vectorstore = vstore

    docs = [Document(page_content='Hello World')]

    result = await ingestor.ingest(docs=docs, digest=digest_str)
    assert result is not None
    assert vstore.add_documents.call_count == 1
