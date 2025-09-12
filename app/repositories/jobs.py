from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.metadata.schemas import ProposedMetadata
from app.schemas.upload import JobStatus
from app.repositories.schemas import (
    CreateJobCmd,
    JobDocumentRefs,
    JobStatusSnapshot,
    JobProgressSnapshot,
)
from app.repositories.models import JobRecord


class Job:
    @staticmethod
    async def create(session: AsyncSession, *, job: CreateJobCmd) -> UUID:
        logger.debug(
            f'Creating job with status {job.status}, percent {job.percent}, step {job.step}'
        )
        user_id = session.info['user_id']
        tenant_id = session.info['tenant_id']
        if not (user_id and tenant_id):
            raise Exception('Missing user_id in session')
        new_id = uuid4()

        rec = JobRecord(
            id=new_id,
            created_by=user_id,
            tenant_id=tenant_id,
            status=job.status.value
            if hasattr(job.status, 'value')
            else str(job.status),
            percent=job.percent,
            step=job.step,
            proposed_metadata=(
                job.proposed_metadata.model_dump(mode='json')
                if job.proposed_metadata is not None
                else None
            ),
            digest=job.digest,
            document_uuid=job.document_uuid,
            collection=job.collection,
            original_filename=job.original_filename,
            content_type=job.content_type,
            size_bytes=job.size_bytes,
        )
        try:
            session.add(rec)
            await session.commit()
        except Exception as e:
            await session.rollback()
            raise Exception(f'Failed to create job: {e}')
        return new_id

    @staticmethod
    async def update_progress(
        session: AsyncSession,
        *,
        job_id: UUID,
        percent: int,
        step: str | None,
    ) -> None:
        try:
            rec = await session.get(JobRecord, job_id)
            if rec is None:
                logger.warning(f'Job {job_id} not found for progress update')
                return
            rec.percent = percent
            rec.step = step
            rec.updated_at = datetime.now(timezone.utc)
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error(f'Failed to update progress for job {job_id}: {e}')

    @staticmethod
    async def update_status(
        session: AsyncSession,
        *,
        job_id: UUID,
        status: JobStatus,
        proposed_metadata: ProposedMetadata | None = None,
        percent: int | None = None,
        step: str | None = None,
    ) -> None:
        try:
            rec = await session.get(JobRecord, job_id)
            if rec is None:
                raise Exception(f'Job {job_id} not found')
            rec.status = status.value if hasattr(status, 'value') else str(status)
            if percent is not None:
                rec.percent = percent
            if step is not None:
                rec.step = step
            if proposed_metadata is not None:
                rec.proposed_metadata = proposed_metadata.model_dump(mode='json')
            rec.updated_at = datetime.now(timezone.utc)
            await session.commit()
        except Exception as e:
            await session.rollback()
            raise Exception(f'Failed to update status for job {job_id}: {e}')

    @staticmethod
    async def finalize(
        session: AsyncSession,
        *,
        job_id: UUID,
        status=JobStatus.COMPLETED,
    ) -> None:
        await Job.update_status(
            session, job_id=job_id, status=status, percent=100, step=''
        )

    @staticmethod
    async def get_status(
        session: AsyncSession, *, job_id: UUID
    ) -> JobStatusSnapshot | None:
        rec = await session.get(JobRecord, job_id)
        if rec is None:
            return None
        # Try to rehydrate ProposedMetadata if possible
        proposed = None
        pm = rec.proposed_metadata
        if pm is not None:
            try:
                if isinstance(pm, str):
                    import json as _json

                    pm = _json.loads(pm)
                if isinstance(pm, dict):
                    from app.metadata.schemas import ProposedMetadata as _PM

                    proposed = _PM(**pm)
            except Exception:
                proposed = None
        return JobStatusSnapshot(
            job_id=rec.id,
            status=JobStatus(rec.status)
            if not isinstance(rec.status, JobStatus)
            else rec.status,
            progress=JobProgressSnapshot(percent=rec.percent or 0, step=rec.step),
            original_filename=rec.original_filename,
            proposed_metadata=proposed,
            warnings=rec.warnings or [],
            errors=rec.errors or [],
        )

    @staticmethod
    async def get_job_document_refs(
        session: AsyncSession, *, job_id: UUID
    ) -> JobDocumentRefs | None:
        rec = await session.get(JobRecord, job_id)
        if rec is None:
            return None
        return JobDocumentRefs(
            digest=rec.digest,
            collection=rec.collection,
            document_uuid=rec.document_uuid,
        )

    @staticmethod
    async def delete(session: AsyncSession, *, job_id: UUID) -> bool:
        """Delete a job by job_id.

        Uses ORM delete/commit to remove the job.
        Returns True if a row was deleted; False otherwise.
        """
        try:
            rec = await session.get(JobRecord, job_id)
            if rec is None:
                return False
            await session.delete(rec)
            await session.commit()
            return True
        except Exception as e:
            await session.rollback()
            logger.error(f'Failed to delete job {job_id}: {e}')
            return False
