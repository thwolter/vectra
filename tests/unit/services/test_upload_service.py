import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, create_autospec

from fastapi import UploadFile
from tenauth.schemas import AccessContext

from app.api.file import TemporaryUploadFile
from app.schemas.upload import ContinueProcessingInput, JobStatus, StartUploadInput
from app.services.job_service import JobService
from app.services.upload_service import UploadService
from app.services.upload_steps import UploadPipeline


async def test_continue_processing_calls_all_upload_handlers(
    tiny_pdf_upload: UploadFile, digest_random, session, upload_service
):
    pipeline = create_autospec(UploadPipeline, instance=True, spec_set=True)

    async def _return_ctx(ctx, *args, **kwargs):
        return ctx

    pipeline.store_original.side_effect = _return_ctx
    pipeline.parse_document.side_effect = _return_ctx
    pipeline.store_markdown.side_effect = _return_ctx
    pipeline.ingest_documents.side_effect = _return_ctx
    pipeline.update_document_uris.side_effect = _return_ctx

    job_service = create_autospec(JobService, instance=True, spec_set=True)

    upload_service.pipeline = pipeline
    upload_service.job_service = job_service

    process_input = ContinueProcessingInput(
        job_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        digest=digest_random,
        file=TemporaryUploadFile.from_upload(tiny_pdf_upload),
        access_context=AccessContext.from_session(session),
    )

    await upload_service.continue_processing(payload=process_input)

    # Verify each pipeline step was awaited exactly once
    assert pipeline.store_original.await_count == 1
    assert pipeline.parse_document.await_count == 1
    assert pipeline.store_markdown.await_count == 1
    assert pipeline.ingest_documents.await_count == 1
    assert pipeline.update_document_uris.await_count == 1

    # Each step should receive the evolving JobCtx instance
    ctx_arg = pipeline.store_original.await_args.args[0]
    assert ctx_arg.job_id == process_input.job_id
    assert pipeline.parse_document.await_args.args[0].job_id == process_input.job_id
    assert pipeline.store_markdown.await_args.args[0].job_id == process_input.job_id
    ingest_ctx = pipeline.ingest_documents.await_args.args[0]
    assert ingest_ctx.job_id == process_input.job_id
    from sqlmodel.ext.asyncio.session import AsyncSession

    assert isinstance(pipeline.ingest_documents.await_args.kwargs['session'], AsyncSession)

    update_ctx = pipeline.update_document_uris.await_args.args[0]
    assert update_ctx.job_id == process_input.job_id
    assert isinstance(pipeline.update_document_uris.await_args.kwargs['session'], AsyncSession)


async def test_initiate_document_intake_returns_duplicate(session, tiny_pdf_upload):
    pipeline = create_autospec(UploadPipeline, instance=True, spec_set=True)
    service = UploadService(collection='default', pipeline=pipeline)

    document_record = SimpleNamespace(id=uuid.uuid4())
    service.document_service.ensure_canonical_document = AsyncMock(return_value=(document_record, False))

    existing_job_id = uuid.uuid4()
    ingestion = SimpleNamespace(job_id=existing_job_id)
    service._find_existing_ingestion = AsyncMock(return_value=ingestion)  # type: ignore[attr-defined]

    job_record = SimpleNamespace(id=existing_job_id, status=JobStatus.COMPLETED.value)
    service._fetch_job_by_id = AsyncMock(return_value=job_record)  # type: ignore[attr-defined]

    payload = StartUploadInput(file=TemporaryUploadFile.from_upload(tiny_pdf_upload))

    response = await service.initiate_document_intake(session, payload=payload)

    assert response.status == JobStatus.DUPLICATED
    assert response.job_id == existing_job_id

    payload.file.close()
