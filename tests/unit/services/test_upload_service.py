import uuid
from unittest.mock import create_autospec

from fastapi import UploadFile

from app.api.file import TemporaryUploadFile
from app.api.schemas import AccessContext
from app.schemas.upload import ContinueProcessingInput
from app.services.job_service import JobService
from app.services.upload_steps import UploadPipeline


async def test_continue_processing_calls_all_upload_handlers(
    tiny_pdf_upload: UploadFile, digest_random, session, upload_service
):
    pipeline = create_autospec(UploadPipeline, instance=True, spec_set=True)

    async def _return_ctx(ctx, *args, **kwargs):
        return ctx

    async def _return_ctx_with_session(ctx, *args, **kwargs):
        return ctx

    pipeline.store_original.side_effect = _return_ctx
    pipeline.parse_document.side_effect = _return_ctx
    pipeline.store_markdown.side_effect = _return_ctx
    pipeline.enrich_docs_metadata.side_effect = _return_ctx
    pipeline.ingest_documents.side_effect = _return_ctx_with_session
    pipeline.extract_metadata.side_effect = _return_ctx_with_session
    pipeline.persist_metadata.side_effect = _return_ctx_with_session
    pipeline.update_document_uris.side_effect = _return_ctx_with_session

    job_service = create_autospec(JobService, instance=True, spec_set=True)

    upload_service.pipeline = pipeline
    upload_service.job_service = job_service

    process_input = ContinueProcessingInput(
        job_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        digest=digest_random,
        file=TemporaryUploadFile.from_upload(tiny_pdf_upload),
        hints=None,
        access_context=AccessContext.from_session(session).model_dump(),
    )

    await upload_service.continue_processing(payload=process_input)

    # Verify each pipeline step was awaited exactly once
    assert pipeline.store_original.await_count == 1
    assert pipeline.parse_document.await_count == 1
    assert pipeline.store_markdown.await_count == 1
    assert pipeline.enrich_docs_metadata.await_count == 1
    assert pipeline.ingest_documents.await_count == 1
    assert pipeline.extract_metadata.await_count == 1
    assert pipeline.persist_metadata.await_count == 1
    assert pipeline.update_document_uris.await_count == 1

    # Each step should receive the evolving JobCtx instance
    ctx_arg = pipeline.store_original.await_args.args[0]
    assert ctx_arg.job_id == process_input.job_id
    assert pipeline.parse_document.await_args.args[0].job_id == process_input.job_id
    assert pipeline.store_markdown.await_args.args[0].job_id == process_input.job_id
    assert pipeline.enrich_docs_metadata.await_args.args[0].job_id == process_input.job_id
    ingest_ctx = pipeline.ingest_documents.await_args.args[0]
    assert ingest_ctx.job_id == process_input.job_id
    from sqlmodel.ext.asyncio.session import AsyncSession

    assert isinstance(pipeline.ingest_documents.await_args.kwargs['session'], AsyncSession)

    persist_ctx = pipeline.persist_metadata.await_args.args[0]
    assert persist_ctx.job_id == process_input.job_id
    assert isinstance(pipeline.persist_metadata.await_args.kwargs['session'], AsyncSession)
    assert pipeline.persist_metadata.await_args.kwargs['update_embeddings'] is False

    # Extract metadata step assertions
    extract_ctx = pipeline.extract_metadata.await_args.args[0]
    assert extract_ctx.job_id == process_input.job_id
    assert isinstance(pipeline.extract_metadata.await_args.kwargs['session'], AsyncSession)

    update_ctx = pipeline.update_document_uris.await_args.args[0]
    assert update_ctx.job_id == process_input.job_id
    assert isinstance(pipeline.update_document_uris.await_args.kwargs['session'], AsyncSession)
