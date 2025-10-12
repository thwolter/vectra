import pytest
from langchain_core.documents import Document

from app.api.file import TemporaryUploadFile
from app.repositories import EmbeddingsRepository
from app.schemas.jobs import JobCtx


@pytest.mark.integration
@pytest.mark.needs_postgres
async def test_ingest_documents_sets_chunk_metadata(session, upload_pipeline, tiny_pdf_upload, job_created):
    file = TemporaryUploadFile.from_upload(tiny_pdf_upload)
    digest = job_created.document.digest
    collection = upload_pipeline.ingestor.collection

    doc = Document(page_content='hello world', metadata={})
    ctx = JobCtx(
        job_id=job_created.id,
        collection=collection,
        file=file,
        document_id=job_created.document_id,
        digest=digest,
        docs=[doc],
    )

    result = await upload_pipeline.ingest_documents(ctx, session)

    assert result.skip_embed is False

    metadata = await EmbeddingsRepository.get_metadata(session, digest=digest, collection=collection)
    assert metadata, 'Expected embeddings metadata to be created'
    for md in metadata:
        assert md.get('digest') == digest
        assert 'chunk_id' in md


@pytest.mark.integration
@pytest.mark.needs_postgres
async def test_ingest_documents_skips_when_already_exists(session, upload_pipeline, tiny_pdf_upload, job_created):
    file = TemporaryUploadFile.from_upload(tiny_pdf_upload)
    digest = job_created.document.digest
    collection = upload_pipeline.ingestor.collection

    doc = Document(page_content='hello world', metadata={})
    ctx = JobCtx(
        job_id=job_created.id,
        collection=collection,
        file=file,
        document_id=job_created.document_id,
        digest=digest,
        docs=[doc],
    )

    await upload_pipeline.ingest_documents(ctx, session)
    result = await upload_pipeline.ingest_documents(ctx, session)

    assert result.skip_embed is True
