import pytest
from langchain_core.documents import Document

from api.file import TemporaryUploadFile
from schemas.jobs import JobCtx
from services.upload_steps import UploadPipeline
from store.providers import default_store_provider


@pytest.mark.integration
async def test_ingest_documents_skips_when_already_exists(auth_session, tiny_pdf_upload, job_created):
    file = TemporaryUploadFile.from_upload(tiny_pdf_upload)
    digest = job_created.document.digest
    collection = 'test'

    doc = Document(page_content='hello world', metadata={})
    ctx = JobCtx(
        job_id=job_created.id,
        tenant_id=job_created.tenant_id,
        collection=collection,
        file=file,
        document_id=job_created.document_id,
        digest=digest,
        docs=[doc],
    )

    store = default_store_provider(collection=collection)
    pipeline = UploadPipeline(store=store)
    await pipeline.ingest_documents(ctx, auth_session)
    result = await pipeline.ingest_documents(ctx, auth_session)

    assert result.skip_embed is True
