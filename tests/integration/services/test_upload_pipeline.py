import uuid

import pytest
from langchain_core.documents import Document

from app.api.file import TemporaryUploadFile
from app.metadata.schemas import NoopHints, FinanceReportHints
from app.schemas.jobs import JobCtx
from app.repositories import EmbeddingsRepository



async def _prepare_vectorstore_doc(session, vectorstore_factory, collection: str, digest: str, source: str = 'test'):
    """Insert a minimal document into the vector store for the given digest.

    This avoids running the full pipeline while still providing retrieval context
    for the extraction agent. Content mentions a plausible company/year/type.
    """
    # Idempotency: only add if no embeddings exist for this digest+source+collection
    exists = await EmbeddingsRepository.exists(session, collection=collection, digest=digest, source=source)
    if exists:
        return
    vs = vectorstore_factory(collection)
    text = (
        "Apple Inc. Quarterly Report (Form 10-Q) for the fiscal year 2024. "
        "This document is an SEC filing describing Apple results."
    )
    md = {
        'digest': digest,
        'source': source,
        'collection': collection,
    }
    doc = Document(page_content=text, metadata=md)
    vs.add_documents(documents=[doc])


@pytest.mark.integration
@pytest.mark.needs_postgres
@pytest.mark.parametrize('hints', [NoopHints(), FinanceReportHints()])
async def test_extract_metadata_only(session, upload_pipeline, apple_report_first_page_upload, vectorstore_factory, hints):
    # Arrange: build a JobCtx with minimal required fields
    file = TemporaryUploadFile.from_upload(apple_report_first_page_upload)
    digest = await file.sha256_b64()
    collection = upload_pipeline.ingestor.collection

    # Provide something in the vector store to retrieve against for this digest
    await _prepare_vectorstore_doc(session, vectorstore_factory, collection=collection, digest=digest)

    ctx = JobCtx(
        job_id=uuid.uuid4(),
        collection=collection,
        file=file,
        hints=hints,
        document_id=uuid.uuid4(),
        digest=digest,
    )

    # Act: run only the extract step
    result = await upload_pipeline.extract_metadata(ctx, session)

    # Assert: proposed metadata is present and merged into ctx.metadata
    assert result.proposed_metadata is not None, 'Expected proposed metadata from extraction agent'
    # metadata should be a dict (may be empty depending on model), and needs_review is boolean
    assert isinstance(result.metadata, (dict, type(None)))
    assert isinstance(result.needs_review, bool)

    # If model extracted fields, they should be under the flattened metadata
    if result.metadata:
        md = result.metadata
        # Keys may be missing if model fails; in that case, needs_review should be True
        for k in ('company', 'financial_year', 'document_type'):
            if k not in md or md.get(k) in (None, ''):
                assert result.needs_review is True
                break
