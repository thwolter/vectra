from __future__ import annotations

import asyncio
from dataclasses import dataclass
from functools import partial
from typing import Awaitable, Callable
from uuid import UUID

from loguru import logger
from sqlmodel.ext.asyncio.session import AsyncSession
from tenauth.session import access_scoped_session_ctx

from core.db import session_factory
from repositories import ingestion_repository, job_repository
from repositories.models import DocumentRecord, JobRecord
from repositories.schemas import DocumentCreate, IngestionVersion, JobCreate
from schemas.jobs import JobCtx
from schemas.upload import (
    ContinueProcessingInput,
    JobStatus,
    StartUploadInput,
    UploadInitResponse,
)

from .document_service import DocumentService
from .job_service import JobService
from .upload_steps import UploadPipeline
from .utils import build_job_ctx


@dataclass(frozen=True)
class _Step:
    percent: int
    step: str
    call: Callable[[JobCtx], Awaitable[JobCtx]]


class UploadService:
    """Ingestion service orchestrating upload → parse → store → embed."""

    def __init__(
        self,
        *,
        collection: str,
        pipeline: UploadPipeline,
        document_service: DocumentService | None = None,
        job_service: JobService | None = None,
    ) -> None:
        self.collection = collection
        self.pipeline = pipeline
        self.job_service = job_service or JobService()
        self.document_service = document_service or DocumentService()
        self.ingestion_repo = ingestion_repository
        self.job_repo = job_repository

    async def _ensure_document(
        self, session: AsyncSession, *, payload: StartUploadInput, digest: str
    ) -> tuple[DocumentRecord, bool]:
        return await self.document_service.ensure_canonical_document(
            session,
            data=DocumentCreate(
                collection=self.collection,
                digest=digest,
                original_filename=payload.file.filename,
                content_type=payload.file.content_type,
                size_bytes=payload.file.size,
            ),
        )

    async def _create_job(self, session: AsyncSession, *, document_id: UUID) -> JobRecord:
        return await self.job_service.init_job(
            session,
            job=JobCreate(
                document_id=document_id,
            ),
        )

    def _ingestion_fingerprint(self) -> str:
        return IngestionVersion.from_settings(collection=self.collection).fingerprint()

    async def _find_existing_ingestion(self, session: AsyncSession, *, digest: str):
        fingerprint = self._ingestion_fingerprint()
        return await self.ingestion_repo.find(
            session,
            fingerprint=fingerprint,
            collection=self.collection,
            digest=digest,
        )

    async def _fetch_job_by_id(self, session: AsyncSession, *, job_id: UUID | None) -> JobRecord | None:
        if not job_id:
            return None
        try:
            return await self.job_repo.get(session, job_id=job_id)
        except Exception:
            return None

    async def _resolve_existing_job(
        self,
        session: AsyncSession,
        *,
        document_id: UUID,
        digest: str,
    ) -> tuple[JobRecord | None, bool]:
        job = await self.job_service.get_pending_job(session, document_id=document_id)
        if job:
            return job, True

        ingestion = await self._find_existing_ingestion(session, digest=digest)
        if ingestion and ingestion.job_id:
            job = await self._fetch_job_by_id(session, job_id=ingestion.job_id)
            if job and JobStatus(job.status) in {JobStatus.QUEUED, JobStatus.PROCESSING}:
                return job, True
            return job, False

        return None, False

    async def initiate_document_intake(self, session: AsyncSession, *, payload: StartUploadInput) -> UploadInitResponse:
        """Initialize a job and immediately return UploadInitResponse.

        Heavy processing continues asynchronously in the background.
        """

        digest = await payload.file.sha256_b64()
        document, created = await self._ensure_document(session, payload=payload, digest=digest)

        if not created:
            ingestion = await self._find_existing_ingestion(session, digest=digest)
            if ingestion:
                existing_job = (
                    await self._fetch_job_by_id(session, job_id=ingestion.job_id) if ingestion.job_id else None
                )
                existing_completed = existing_job and JobStatus(existing_job.status) == JobStatus.COMPLETED
                if existing_completed or existing_job is None:
                    job_id = existing_job.id if existing_job else ingestion.job_id or document.id
                    return UploadInitResponse(
                        job_id=job_id,
                        document_id=document.id,
                        status=JobStatus.DUPLICATED,
                        digest=digest,
                        original_filename=payload.file.filename,
                        already_running=False,
                    )

        if created:
            job = await self._create_job(session, document_id=document.id)
            already_running = False
        else:
            job, already_running = await self._resolve_existing_job(
                session,
                document_id=document.id,
                digest=digest,
            )
            if not job:
                job = await self._create_job(session, document_id=document.id)

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

        async with access_scoped_session_ctx(
            session_factory=session_factory,
            access_context=payload.access_context,
        ) as session:
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
