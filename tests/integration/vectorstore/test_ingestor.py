import pytest

from schemas.enums import CollectionEnum
from vector.factory import get_vectorstore
from vector.ingestor import DocumentIngestor


@pytest.fixture
def ingestor() -> DocumentIngestor:
    """Create DocumentIngestor instance for testing."""
    return DocumentIngestor(collection=CollectionEnum.DEFAULT.value)


@pytest.mark.needs_openai
async def test_ingest_creates_embeddings(ingestor, sample_documents, digest_random, auth_session, job_created):
    """Test that ingest method creates embeddings in the vector."""
    # Use only first 2 documents for faster testing

    test_docs = sample_documents[:2]
    await ingestor.ingest(auth_session, docs=test_docs, job_id=job_created.id)

    # Search for content from the first document
    first_doc_content = test_docs[0].page_content[:100]  # First 100 chars
    vs = get_vectorstore(collection=CollectionEnum.DEFAULT.value, tenant_id=auth_session.info['tenant_id'])
    results = await vs.asimilarity_search(first_doc_content, k=1)

    assert len(results) > 0, 'No documents found in vector after ingestion'
    assert any(first_doc_content[:50] in result.page_content for result in results), (
        'Ingested document content not found in search results'
    )
