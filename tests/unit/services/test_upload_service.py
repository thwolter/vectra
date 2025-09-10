import uuid
from unittest.mock import create_autospec

import pytest
from fastapi import UploadFile

from app.api.file import TemporaryUploadFile
from app.schemas.upload import ContinueProcessingInput
from app.services.job_service import JobService
from app.services.upload_service import UploadService
from app.services.upload_steps import UploadPipeline


@pytest.mark.asyncio
async def test_continue_processing_calls_all_upload_handlers(
    tiny_pdf_upload: UploadFile, digest_str
):
    pipeline = create_autospec(UploadPipeline, instance=True, spec_set=True)
    pipeline.init.return_value = pipeline

    job_service = create_autospec(JobService, instance=True, spec_set=True)

    service = UploadService()
    service.pipeline = pipeline
    service.job_service = job_service

    process_input = ContinueProcessingInput(
        job_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        digest=digest_str,
        file=TemporaryUploadFile.from_upload(tiny_pdf_upload),
        hints=None,
    )

    await service.continue_processing(process_input)

    # Verify each pipeline step was awaited exactly once
    assert pipeline.store_original.await_count == 1
    assert pipeline.parse_document.await_count == 1
    assert pipeline.store_markdown.await_count == 1
    assert pipeline.enrich_docs_metadata.await_count == 1
    assert pipeline.ingest_documents.await_count == 1
    assert pipeline.persist_metadata.await_count == 1
    assert pipeline.update_document_uris.await_count == 1
