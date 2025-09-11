from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.metadata.schemas import ProposedMetadata
from app.repositories.factory import get_embedding_repository, get_job_repository
from app.repositories.job_repository import JobRepository
from app.repositories.embeddings import EmbeddingsRepository
from app.schemas.jobs import InitJob, CreateJob
from app.schemas.upload import (
    JobStatus,
    JobProgress,
    JobStatusResponse,
    JobReviewResponse,
)
from app.schemas.upload import JobReviewPayload


class JobService:
    """Thin service encapsulating job lifecycle and invariants.

    Keeps JobRepository pure persistence; enforces:
    - Canonical initialization defaults
    - Progress clamping and monotonicity
    - Valid status transitions
    - Failure recording helper
    - Typed get_status with ProposedMetadata rehydration
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
        JobStatus.FAILED: {JobStatus.FAILED},
    }

    def __init__(
        self,
        *,
        job_repo: JobRepository | None = None,
        metadata_repo: EmbeddingsRepository | None = None,
        embedded_repo: EmbeddingsRepository | None = None,
    ) -> None:
        self.job_repo = job_repo or get_job_repository()
        self.metadata_repo = metadata_repo or get_embedding_repository()
        self.embeddings_repo = embedded_repo or get_embedding_repository()

    async def init_job(self, session: AsyncSession, *, job: InitJob) -> UUID:
        """Create/init a job row with canonical defaults using schemas.jobs.InitJob.

        Defaults: status=processing, percent=0, step='hash'.
        Optionally guards uniqueness by (collection, digest) if a future repo method exists.
        """
        create = CreateJob(**job.model_dump())
        return await self.job_repo.create_job(session, job=create)

    async def update_progress(
        self,
        session: AsyncSession,
        *,
        job_id: UUID,
        percent: int,
        step: str | None = None,
    ) -> None:
        """Clamp percent to 0-100; ensure monotonicity; normalize empty step to None."""
        norm_step = (step or None) if step else None
        # Fetch existing to enforce monotonic
        current = await self.job_repo.get_status(session=session, job_id=job_id)
        old = int(current.progress.percent) if current else 0
        new_percent = max(old, max(0, min(100, int(percent))))
        await self.job_repo.update_progress(
            session=session, job_id=job_id, percent=new_percent, step=norm_step
        )

    async def update_status(
        self,
        session: AsyncSession,
        *,
        job_id: UUID,
        status: JobStatus,
        proposed_metadata: ProposedMetadata | None = None,
        percent: int | None = None,
        step: str | None = None,
    ) -> None:
        """Enforce valid transitions; normalize fields and persist."""
        cur = await self.job_repo.get_status(session=session, job_id=job_id)
        cur_status = (
            JobStatus(cur.status) if cur and cur.status else JobStatus.PROCESSING
        )
        allowed = self._ALLOWED.get(cur_status, set())
        if status not in allowed:
            raise ValueError(
                f'Invalid job status transition {cur_status.value} -> {status.value}'
            )

        norm_percent, norm_step = self.normalise_progress(step, percent, status)

        await self.job_repo.update_status(
            session=session,
            job_id=job_id,
            status=status,
            proposed_metadata=proposed_metadata,
            percent=norm_percent,
            step=norm_step,
        )

    @staticmethod
    def normalise_progress(step, percent, status):
        if status == JobStatus.COMPLETED:
            return 100, ''
        else:
            if step is None or step == '':
                norm_step = None
            else:
                norm_step = step
            if percent is None:
                norm_percent = None
            else:
                norm_percent = max(0, min(100, int(percent)))
            return norm_percent, norm_step

    async def fail_job(
        self,
        session: AsyncSession,
        *,
        job_id: UUID,
        exc: Exception,
        last_step: str | None = None,
    ) -> None:
        """Record failure with exception text and optional last step."""
        await self.job_repo.update_status(
            session=session,
            job_id=job_id,
            status=JobStatus.FAILED,
            step=last_step or None,
        )

    async def get_status(
        self, session: AsyncSession, *, job_id: UUID
    ) -> JobStatusResponse:
        data = await self.job_repo.get_status(session=session, job_id=job_id)
        if data is None:
            return JobStatusResponse(
                job_id=job_id,
                status=JobStatus.FAILED,
                progress=JobProgress(percent=0, step=None),
                errors=['job_not_found'],
            )

        return data

    async def _apply_corrections_to_embeddings(
        self, session: AsyncSession, *, job_id, proposed_obj
    ) -> bool:
        refs = await self.job_repo.get_job_document_refs(session=session, job_id=job_id)
        if refs:
            meta_payload = proposed_obj.metadata or {}
            if hasattr(meta_payload, 'model_dump'):
                meta_payload = meta_payload.model_dump(exclude_none=True)  # type: ignore[attr-defined]
            if not isinstance(meta_payload, dict):
                meta_payload = {}
            await self.embeddings_repo.update_metadata(
                digest=refs.digest,
                collection=refs.collection,
                metadata=meta_payload,
            )
            return True
        return False

    @staticmethod
    async def _apply_corrections(
        *, status: JobStatusResponse, payload: JobReviewPayload
    ):
        if status.proposed_metadata is None:
            return None
        meta_dict = status.proposed_metadata.metadata or {}
        if payload.corrections:
            meta_dict.update(
                {k: v for k, v in payload.corrections.items() if v is not None}
            )
        # Rebuild ProposedMetadata with merged metadata
        return ProposedMetadata(
            metadata=meta_dict,
            confidence=status.proposed_metadata.confidence or {},
            conflicts=[],  # assume conflicts resolved after human review
        )

    async def review_job(
        self, session: AsyncSession, *, job_id: UUID, payload: JobReviewPayload
    ) -> JobReviewResponse:
        status = await self.get_status(session=session, job_id=job_id)
        new_status = JobStatus.COMPLETED if payload.confirm else JobStatus.NEEDS_REVIEW
        proposed_obj = await self._apply_corrections(status=status, payload=payload)

        if new_status is JobStatus.COMPLETED and proposed_obj is not None:
            await self._apply_corrections_to_embeddings(
                session=session, job_id=job_id, proposed_obj=proposed_obj
            )

        # Update job status with (possibly corrected) proposed metadata
        await self.update_status(
            session=session,
            job_id=job_id,
            status=new_status,
            proposed_metadata=proposed_obj,
        )
        return JobReviewResponse(job_id=job_id, status=new_status)

    async def delete_job(self, session: AsyncSession, *, job_id: UUID) -> bool:
        """Delete a job by job_id."""
        return await self.job_repo.delete(session, job_id=job_id)
