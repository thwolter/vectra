from __future__ import annotations

from dataclasses import dataclass
from functools import partial
from typing import Any, Awaitable, Callable
from uuid import UUID

from loguru import logger
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.dependencies import access_scoped_session_ctx
from app.metadata.base import Strategy
from app.repositories.schemas import DocumentCreate, JobCreate
from app.schemas.upload import (
    ContinueProcessingInput,
    JobStatus,
    StartUploadInput,
    UploadInitResponse,
)
from app.utils.job import build_job_ctx

from .document_service import DocumentService
from .job_service import JobService
from .upload_steps import UploadPipeline


@dataclass(frozen=True)
class _Step:
    percent: int
    step: str
    call: Callable[[], Awaitable[Any]]


class UploadService:
    """Ingestion service orchestrating upload → parse → store → embed."""

    def __init__(self, *, collection: str, pipeline: UploadPipeline) -> None:
        self.collection = collection
        self.pipeline = pipeline
        self.job_service = JobService()

    async def initiate_document_intake(self, session: AsyncSession, *, payload: StartUploadInput) -> UploadInitResponse:
        """Initialize a job and immediately return UploadInitResponse.

        Heavy processing continues asynchronously in the background.
        """

        digest = await payload.file.sha256_b64()
        document_service = DocumentService()
        already_running = False

        document, created = await document_service.ensure_canonical_document(
            session,
            data=DocumentCreate(
                collection=self.collection,
                digest=digest,
                original_filename=payload.file.filename,
                content_type=payload.file.content_type,
                size_bytes=payload.file.size,
            ),
        )

        # Prepare proposed metadata once (used only when creating a fresh job)
        strategy: Strategy = Strategy.from_hints(payload.hints)
        proposed_metadata = strategy.proposed_metadata()

        if created:
            # New document -> always create a new job
            job = await self.job_service.init_job(
                session,
                job=JobCreate(
                    document_id=document.id,
                    proposed_metadata=proposed_metadata,
                ),
            )
        else:
            # Existing document: try to reuse a still-active job (enforced by partial unique index)
            job, created = await self.job_service.get_pending_or_create(
                session,
                document_id=document.id,
                collection=self.collection,
                proposed_metadata=proposed_metadata,
            )
            already_running = created

        return UploadInitResponse(
            job_id=job.id,
            document_id=document.id,
            status=JobStatus(job.status),
            digest=digest,
            original_filename=payload.file.filename,
            already_running=already_running,
        )

    async def _run_step(self, session: AsyncSession, job_id: UUID, step: _Step) -> bool:
        await self.job_service.update_progress(session, job_id=job_id, percent=step.percent, step=step.step)
        try:
            await step.call()
            return True
        except Exception as e:
            logger.exception(f'Background processing failed for job {job_id} ({step.step}): {e}')
            await self.job_service.fail_job(session, job_id=job_id, exc=e, last_step=step.step)
            return False

    async def continue_processing(
        self,
        payload: ContinueProcessingInput,
    ) -> None:
        """Perform the heavy processing steps for an initialized job.

        This uses precomputed identifiers from the initialization step
        and is intended to be scheduled via the Dramatiq task queue.
        """

        init_ctx = build_job_ctx(payload=payload, collection=self.collection)
        pipeline = self.pipeline.init(init_ctx)
        job_id = init_ctx.job_id

        async with access_scoped_session_ctx(payload.access_context) as session:
            steps: list[_Step] = [
                _Step(10, 'store_original', pipeline.store_original),
                _Step(20, 'parse', pipeline.parse_document),
                _Step(50, 'store_markdown', pipeline.store_markdown),
                _Step(60, 'prepare_metadata', pipeline.enrich_docs_metadata),
                _Step(70, 'ingest', partial(pipeline.ingest_documents, session=session)),
                _Step(
                    90,
                    'ensure_metadata',
                    partial(pipeline.persist_metadata, session=session, update_embeddings=False),
                ),
                _Step(
                    95,
                    'update_s3_uris',
                    partial(pipeline.update_document_uris, session=session),
                ),
            ]

            for s in steps:
                success = await self._run_step(session, job_id, s)
                if not success:
                    return

            job_status = JobStatus.NEEDS_REVIEW if pipeline.ctx.needs_review else JobStatus.COMPLETED
            await self.job_service.update_status(
                session,
                job_id=job_id,
                status=job_status,
                proposed_metadata=pipeline.ctx.proposed_metadata,
            )
            logger.success(f'Finalized job {job_id}')
