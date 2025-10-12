from __future__ import annotations

from typing import Tuple
from uuid import UUID

from asyncpg import UniqueViolationError
from sqlmodel.ext.asyncio.session import AsyncSession

from app.repositories import JobRepository
from app.repositories.exceptions import RecordNotFoundError
from app.repositories.models import IngestionRecord, JobRecord
from app.repositories.schemas import JobCreate, JobUpdate
from app.schemas.upload import JobProgress, JobStatus, JobStatusResponse

from .utils import normalise_progress


class JobService:
    """Thin service encapsulating job lifecycle and invariants.

    Keeps JobRepository pure persistence; enforces:
    - Canonical initialization defaults
    - Progress clamping and monotonicity
    - Valid status transitions
    - Failure recording helper
    - Typed get_status
    """

    # Status transitions
    _ALLOWED: dict[JobStatus, set[JobStatus]] = {
        JobStatus.QUEUED: {JobStatus.PROCESSING, JobStatus.FAILED},
        JobStatus.PROCESSING: {
            JobStatus.NEEDS_REVIEW,
            JobStatus.COMPLETED,
            JobStatus.FAILED,
        },
        JobStatus.NEEDS_REVIEW: {JobStatus.COMPLETED, JobStatus.FAILED},
        JobStatus.COMPLETED: {JobStatus.COMPLETED},
        JobStatus.FAILED: {JobStatus.FAILED, JobStatus.COMPLETED},
    }

    def __init__(self, job_repository=JobRepository) -> None:
        self.repo = job_repository

    async def init_job(self, session: AsyncSession, *, job: JobCreate) -> JobRecord:
        create = JobCreate(
            status=JobStatus.PROCESSING,
            percent=0,
            step='hash',
            document_id=job.document_id,
        )
        return await self.repo.create(session, job=create)

    async def update_progress(
        self,
        session: AsyncSession,
        *,
        job_id: UUID,
        percent: int,
        step: str | None = None,
    ) -> None:
        """Clamp percent to 0-100; ensure monotonicity; normalize empty step to None."""
        job = await self.repo.get(session=session, job_id=job_id)
        await self.repo.update(
            session,
            job=JobUpdate(
                id=job_id,
                percent=max(job.percent, max(0, min(100, int(percent)))),
                step=(step or None) if step else None,
            ),
        )

    async def update_status(
        self,
        session: AsyncSession,
        *,
        job_id: UUID,
        status: JobStatus,
        percent: int | None = None,
        step: str | None = None,
    ) -> None:
        """Enforce valid transitions; normalize fields and persist."""
        job = await self.repo.get(session=session, job_id=job_id)

        allowed = self._ALLOWED.get(JobStatus(job.status), set())
        if status not in allowed:
            raise ValueError(f'Invalid job status transition {job.status} -> {status.value}')

        norm_percent, norm_step = normalise_progress(step, percent, status)
        data = JobUpdate(
            id=job_id,
            status=status,
            percent=norm_percent,
            step=norm_step,
        )
        await self.repo.update(session, job=data)

    async def fail_job(
        self,
        session: AsyncSession,
        *,
        job_id: UUID,
        exc: Exception,
        last_step: str | None = None,
    ) -> None:
        """Record failure with exception text and optional last step."""
        await self.repo.update(
            session,
            job=JobUpdate(
                id=job_id,
                status=JobStatus.FAILED,
                step=last_step or None,
            ),
        )

    async def get_status(self, session: AsyncSession, *, job_id: UUID) -> JobStatusResponse:
        try:
            job = await self.repo.get(session=session, job_id=job_id)
        except RecordNotFoundError:
            return JobStatusResponse.job_not_found(job_id=job_id)

        return JobStatusResponse(
            job_id=job.id,
            status=JobStatus(job.status),
            progress=JobProgress(percent=job.percent, step=job.step),
            original_filename=job.document.original_filename,
            warnings=list(job.warnings or []),
            errors=list(job.errors or []),
        )

    async def get_pending_job(self, session: AsyncSession, *, document_id: UUID) -> JobRecord | None:
        job = await self.repo.get_active_for_document(session, document_id=document_id)
        return job

    async def get_pending_or_create(
        self,
        session: AsyncSession,
        *,
        document_id: UUID,
    ) -> Tuple[JobRecord, bool]:
        if job := await self.get_pending_job(session, document_id=document_id):
            return job, False
        try:
            job = await self.init_job(
                session,
                job=JobCreate(
                    document_id=document_id,
                ),
            )
            return job, True
        except UniqueViolationError:
            job = await self.repo.get_active_for_document(session, document_id=document_id)
            if job:
                return job, False
            else:
                raise ValueError(f'No active job found for document {document_id}')

    async def delete_job(self, session: AsyncSession, *, job_id: UUID) -> bool:
        """Delete a job by job_id."""
        return await self.repo.delete(session, job_id=job_id)

    async def ingestion_created(self, session: AsyncSession, *, job_id: UUID, ingestion: IngestionRecord) -> None:
        """Link the newly created ingestion to its job."""
        await self.repo.update(
            session,
            job=JobUpdate(
                id=job_id,
                ingestion_id=ingestion.id,
            ),
        )
