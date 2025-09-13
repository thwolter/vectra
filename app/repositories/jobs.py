from __future__ import annotations

from uuid import UUID, uuid4

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.metadata.schemas import ProposedMetadata
from app.schemas.upload import JobStatus
from app.repositories.schemas import (
    CreateJobCmd,
    JobDocumentRefs,
    JobStatusSnapshot,
    JobProgressSnapshot,
)
from app.repositories.models import JobRecord
from app.utils.types import SHA256B64

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy import literal_column
from datetime import datetime, timezone

from app.repositories.exceptions import JobNotFoundError


class Job:
    @staticmethod
    async def upsert(session: AsyncSession, *, job: CreateJobCmd) -> tuple[UUID, bool]:
        logger.debug(
            f'Creating job with status {job.status}, percent {job.percent}, step {job.step}'
        )
        user_id = session.info['user_id']
        tenant_id = session.info['tenant_id']
        if not (user_id and tenant_id):
            raise Exception('Missing user_id in session')

        proposed_json = None
        if job.proposed_metadata is not None:
            proposed_json = job.proposed_metadata.model_dump(mode='json')

        stmt = (
            insert(JobRecord)
            .values(
                id=uuid4(),
                created_by=user_id,
                tenant_id=tenant_id,
                status=job.status.value,
                percent=job.percent,
                step=job.step,
                proposed_metadata=proposed_json,
                digest=job.digest,
                document_uuid=job.document_uuid,
                collection=job.collection,
                original_filename=job.original_filename,
                content_type=job.content_type,
                size_bytes=job.size_bytes,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            .on_conflict_do_update(
                index_elements=[
                    JobRecord.tenant_id,
                    JobRecord.document_uuid,
                    JobRecord.collection,
                    JobRecord.digest,
                ],
                set_={'id': JobRecord.id},  # no-op to enable RETURNING on conflict
            )
            .returning(
                JobRecord.id,
                literal_column('(xmax = 0)').label('inserted'),
            )
        )

        try:
            res = await session.execute(stmt)
            row = res.one()
            await session.commit()
        except Exception as e:
            await session.rollback()
            raise Exception(f'Failed to create job: {e}')

        job_id = row[0]
        created = bool(row[1])
        return job_id, created

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
                raise JobNotFoundError(f'Job {job_id} not found')
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
    async def status(session: AsyncSession, *, job_id: UUID) -> JobStatusSnapshot:
        rec = await Job.get(session, job_id=job_id)

        proposed = None
        if pm := rec.proposed_metadata:
            proposed = ProposedMetadata(**pm)

        return JobStatusSnapshot(
            job_id=rec.id,
            status=JobStatus(rec.status),
            progress=JobProgressSnapshot(percent=rec.percent or 0, step=rec.step),
            original_filename=rec.original_filename,
            proposed_metadata=proposed,
            warnings=rec.warnings or [],
            errors=rec.errors or [],
        )

    @staticmethod
    async def document_refs(session: AsyncSession, *, job_id: UUID) -> JobDocumentRefs:
        rec = await Job.get(session, job_id=job_id)
        return JobDocumentRefs(
            digest=rec.digest,
            collection=rec.collection,
            document_uuid=rec.document_uuid,
        )

    @staticmethod
    async def delete(session: AsyncSession, *, job_id: UUID) -> bool:
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

    @staticmethod
    async def find(
        session: AsyncSession, *, digest: SHA256B64, collection: str, document_id: UUID
    ) -> UUID | None:
        result = await session.execute(
            select(JobRecord.id).where(
                JobRecord.tenant_id == session.info['tenant_id'],
                JobRecord.collection == collection,
                JobRecord.digest == digest,
                JobRecord.document_uuid == document_id,
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get(session: AsyncSession, *, job_id: UUID) -> JobRecord:
        result: JobRecord | None = await session.get(JobRecord, job_id)
        if result is None:
            raise JobNotFoundError(f'Job {job_id} not found')
        return result
