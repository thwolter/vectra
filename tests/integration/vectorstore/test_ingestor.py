import pytest

from app.schemas.enums import CollectionEnum
from app.vector.ingestor import DocumentIngestor
from app.vector.models import IngestorSettings
from app.repositories import Embeddings
from app.vector.factory import get_vectorstore


@pytest.fixture
def ingestor() -> DocumentIngestor:
    """Create DocumentIngestor instance for testing."""
    ingest_settings = IngestorSettings(max_docs_per_batch=2)
    return DocumentIngestor(
        collection=CollectionEnum.DEFAULT.value, ingest_settings=ingest_settings
    )


@pytest.mark.integration
@pytest.mark.needs_postgres
@pytest.mark.needs_openai
@pytest.mark.asyncio
async def test_ingest_creates_embeddings(
    ingestor, sample_documents, digest_random, session
):
    """Test that ingest method creates embeddings in the vector."""
    # Use only first 2 documents for faster testing

    test_docs = sample_documents[:2]
    await ingestor.ingest(session, docs=test_docs, digest=digest_random)

    # Search for content from the first document
    first_doc_content = test_docs[0].page_content[:100]  # First 100 chars
    vs = get_vectorstore(
        collection=CollectionEnum.DEFAULT.value, tenant_id=session.info['tenant_id']
    )
    results = vs.similarity_search(first_doc_content, k=1)

    assert len(results) > 0, 'No documents found in vector after ingestion'
    assert any(first_doc_content[:50] in result.page_content for result in results), (
        'Ingested document content not found in search results'
    )

    await ingestor.delete_embeddings(session=session, digest=digest_random)


@pytest.mark.integration
@pytest.mark.needs_postgres
@pytest.mark.needs_openai
@pytest.mark.asyncio
async def test_ingest_creates_embeddings_with_metadata(
    ingestor, sample_documents, digest_random, session
):
    """Test that ingest method creates embeddings in the vector."""
    test_docs = sample_documents[:2]

    await ingestor.ingest(session, docs=test_docs, digest=digest_random)
    metadata = await Embeddings.get_metadata(
        session, digest=digest_random, collection=CollectionEnum.DEFAULT.value
    )
    assert metadata[0]['digest'] == digest_random

    await ingestor.delete_embeddings(session, digest=digest_random)


@pytest.mark.integration
def test_batch_documents_with_max_docs_per_batch(ingestor, sample_documents):
    """Test that batch_documents_by_tokens respects max_docs_per_batch=2."""
    # Use all 4 sample documents
    batches = ingestor.batch_documents_by_tokens(sample_documents)

    # With max_docs_per_batch=2, we should get at least 2 batches
    assert len(batches) >= 2, f'Expected at least 2 batches, got {len(batches)}'

    # Each batch should have at most 2 documents
    for i, batch in enumerate(batches):
        assert len(batch) <= 2, f'Batch {i} has {len(batch)} documents, expected max 2'

    # All documents should be included in batches
    total_docs_in_batches = sum(len(batch) for batch in batches)
    assert total_docs_in_batches == len(sample_documents), (
        f'Expected {len(sample_documents)} documents in batches, got {total_docs_in_batches}'
    )
