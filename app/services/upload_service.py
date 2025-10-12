from __future__ import annotations

import asyncio
from dataclasses import dataclass
from functools import partial
from typing import Awaitable, Callable
from uuid import UUID

from loguru import logger
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.dependencies import access_scoped_session_ctx
from app.repositories import IngestionRepository, JobRepository
from app.repositories.schemas import DocumentCreate, IngestionVersion, JobCreate
from app.schemas.jobs import JobCtx
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
    call: Callable[[JobCtx], Awaitable[JobCtx]]


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

        if created:
            # New document -> always create a new job
            job = await self.job_service.init_job(
                session,
                job=JobCreate(
                    document_id=document.id,
                ),
            )
        else:
            job = await self.job_service.get_pending_job(session, document_id=document.id)
            already_running = job is not None

            if not job:
                fingerprint = IngestionVersion.from_settings(collection=self.collection).fingerprint()
                ingestion = await IngestionRepository.find(
                    session,
                    fingerprint=fingerprint,
                    collection=self.collection,
                    digest=digest,
                )

                if ingestion:
                    already_running = True
                    if ingestion.job_id:
                        try:
                            job = await JobRepository.get(session, job_id=ingestion.job_id)
                        except Exception:
                            job = None
                if not job:
                    job = await self.job_service.init_job(
                        session,
                        job=JobCreate(
                            document_id=document.id,
                        ),
                    )

        return UploadInitResponse(
            job_id=job.id,
            document_id=document.id,
            status=JobStatus(job.status),
            digest=digest,
            original_filename=payload.file.filename,
            already_running=already_running,
        )

    async def _run_step(self, session: AsyncSession, job_id: UUID, ctx: JobCtx, step: _Step) -> JobCtx | None:
        await self.job_service.update_progress(session, job_id=job_id, percent=step.percent, step=step.step)
        try:
            return await step.call(ctx)
        except Exception as e:
            logger.exception(f'Background processing failed for job {job_id} ({step.step}): {e}')
            await self.job_service.fail_job(session, job_id=job_id, exc=e, last_step=step.step)
            return None

    async def continue_processing(
        self,
        payload: ContinueProcessingInput,
    ) -> None:
        """Perform the heavy processing steps for an initialized job.

        This uses precomputed identifiers from the initialization step
        and is intended to be scheduled via the Dramatiq task queue.
        """

        logger.debug(f'continue_processing loop_id={id(asyncio.get_running_loop())}')
        ctx = build_job_ctx(payload=payload, collection=self.collection)
        pipeline = self.pipeline
        job_id = ctx.job_id

        async with access_scoped_session_ctx(payload.access_context) as session:
            steps: list[_Step] = [
                _Step(10, 'store_original', pipeline.store_original),
                _Step(30, 'parse', pipeline.parse_document),
                _Step(50, 'store_markdown', pipeline.store_markdown),
                _Step(70, 'ingest', partial(pipeline.ingest_documents, session=session)),
                _Step(90, 'update_s3_uris', partial(pipeline.update_document_uris, session=session)),
            ]

            for s in steps:
                result = await self._run_step(session, job_id, ctx, s)
                if result is None:
                    return
                ctx = result

            await self.job_service.update_status(
                session,
                job_id=job_id,
                status=JobStatus.COMPLETED,
            )
            logger.success(f'Finalized job {job_id}')
