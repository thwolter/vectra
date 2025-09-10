import pytest

from app.extract.agent import extract_metadata
from app.schemas.enums import CollectionEnum
from app.vector.errors import EmbeddingsAlreadyExistError
from app.vector.ingestor import DocumentIngestor
from app.vector.models import IngestorSettings
from app.metadata.schemas import FinanceReportHints, ProposedMetadata


@pytest.fixture
def ingestor():
    return DocumentIngestor(
        CollectionEnum.FINANCIAL, ingest_settings=IngestorSettings(max_docs_per_batch=3)
    )


async def sanitize(sample_documents):
    # Sanity: ensure text contains Apple Inc somewhere
    raw_concat = '\n'.join(
        (getattr(d, 'page_content', '') or '') for d in sample_documents[:50]
    )
    assert ('Apple Inc' in raw_concat) or ('APPLE INC' in raw_concat)

    test_documents = sample_documents
    # Ensure metadata is a dict
    for i, d in enumerate(test_documents):
        d.metadata = d.metadata or {}

    # Pick a document that actually contains 'Apple Inc'
    selected = None
    for d in test_documents:
        text = d.page_content or ''
        if ('Apple Inc' in text) or ('APPLE INC' in text):
            selected = d
            break
    assert selected is not None, "No ingested document contained 'Apple Inc'"

    return test_documents


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_document_info_with_sample_docs(
    sample_documents, ingestor, digest_str
):
    """
    Integration test: ingest sample documents into the vector, then retrieve
    by source and extract metadata. Also verify company equals "Apple Inc".
    """

    test_documents = await sanitize(sample_documents)

    try:
        await ingestor.ingest(
            docs=test_documents,
            digest=digest_str,
        )
    except EmbeddingsAlreadyExistError:
        pass

    result = await extract_metadata(
        digest=digest_str,
        collection=CollectionEnum.FINANCIAL,
        hints=FinanceReportHints(),
    )

    assert isinstance(result, ProposedMetadata)
    md_all = result.metadata or {}
    assert isinstance(md_all, dict) and 'metadata' in md_all and 'evidence' in md_all
    md = md_all['metadata']
    assert md.get('company') in ['Apple Inc.', 'Apple Inc']
    assert md.get('financial_year') == 2024
    assert md.get('document_type') is not None
    assert str(md.get('document_type')) in ['Form 10-K', '10-K', 'Annual Report']
