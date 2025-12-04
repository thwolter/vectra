from __future__ import annotations

import asyncio
from dataclasses import dataclass
from dataclasses import replace as dc_replace
from functools import partial
from typing import Awaitable, Callable
from uuid import UUID

from loguru import logger
from sqlmodel.ext.asyncio.session import AsyncSession
from tenauth.session import access_scoped_session_ctx

from core.db import session_factory
from repositories import ingestion_repository, job_repository
from repositories.exceptions import RecordNotFoundError
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

    def _current_version(self) -> IngestionVersion:
        return IngestionVersion.from_settings(collection=self.collection)

    async def _find_matching_ingestion(
        self,
        session: AsyncSession,
        *,
        digest: str,
        version: IngestionVersion | None = None,
    ):
        version = version or self._current_version()
        return await self.ingestion_repo.find(
            session,
            collection=self.collection,
            digest=digest,
            version=version,
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

        version = self._current_version()
        ingestion = await self._find_matching_ingestion(session, digest=digest, version=version)
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
        current_version = self._current_version()
        document, created = await self._ensure_document(session, payload=payload, digest=digest)

        if not created:
            ingestion = await self._find_matching_ingestion(session, digest=digest, version=current_version)
            if ingestion:
                existing_job = (
                    await self._fetch_job_by_id(session, job_id=ingestion.job_id) if ingestion.job_id else None
                )
                if existing_job:
                    completed = JobStatus(existing_job.status) == JobStatus.COMPLETED
                    return UploadInitResponse(
                        job_id=existing_job.id,
                        document_id=document.id,
                        status=JobStatus.DUPLICATED,
                        digest=digest,
                        original_filename=payload.file.filename,
                        already_running=not completed,
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

    async def _rollback_canceled_job(self, session: AsyncSession, ctx: JobCtx) -> None:
        """Remove any document artifacts created before a cancellation signal."""

        try:
            await self.document_service.delete(session, document_id=ctx.document_id)
        except RecordNotFoundError:
            logger.debug('Document %s already removed while rolling back job %s', ctx.document_id, ctx.job_id)
        except Exception as exc:
            logger.error(
                'Failed to rollback artifacts for canceled job %s (%s): %s',
                ctx.job_id,
                ctx.document_id,
                exc,
            )

    async def _run_step(self, session: AsyncSession, job_id: UUID, ctx: JobCtx, step: _Step) -> JobCtx | None:
        try:
            await self.job_service.update_progress(session, job_id=job_id, percent=step.percent, step=step.step)
            return await step.call(ctx)
        except RecordNotFoundError:
            logger.info('Job %s no longer active; rolling back processed artifacts.', job_id)
            await self._rollback_canceled_job(session, ctx)
            return None
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
            current_version = self._current_version()
            existing_ingestion = await self.ingestion_repo.find(
                session,
                collection=self.collection,
                digest=ctx.digest,
            )
            plan = current_version.plan_for(existing_ingestion)
            ctx = dc_replace(
                ctx,
                ingestion_version=current_version,
                ingestion_plan=plan,
                existing_ingestion=existing_ingestion,
                run_parser=plan.run_parser,
                run_chunker=plan.run_chunker,
                run_embedding=plan.run_embedding,
            )

            steps: list[_Step] = [
                _Step(10, 'store_original', pipeline.store_original),
                _Step(30, 'parse', pipeline.parse_document),
                _Step(50, 'chunk', pipeline.chunk_documents),
                _Step(60, 'store_markdown', pipeline.store_markdown),
                _Step(80, 'ingest', partial(pipeline.ingest_documents, session=session)),
                _Step(90, 'update_s3_uris', partial(pipeline.update_document_uris, session=session)),
            ]

            for s in steps:
                if not await self.job_service.is_job_active(session, job_id=job_id):
                    logger.info(
                        'Job %s canceled before executing %s; rolling back artifacts.',
                        job_id,
                        s.step,
                    )
                    await self._rollback_canceled_job(session, ctx)
                    return

                result = await self._run_step(session, job_id, ctx, s)
                if result is None:
                    return
                ctx = result

            try:
                await self.job_service.update_status(
                    session,
                    job_id=job_id,
                    status=JobStatus.COMPLETED,
                )
            except RecordNotFoundError:
                logger.info('Job %s canceled before completion; rolling back artifacts.', job_id)
                await self._rollback_canceled_job(session, ctx)
                return
            logger.success(f'Finalized job {job_id}')
