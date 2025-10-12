from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from loguru import logger
from sqlalchemy import or_
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from tenauth.schemas import AccessContext

from app.repositories.models import IngestionRecord, JobRecord
from app.repositories.schemas import JobCreate, JobUpdate
from app.schemas.upload import JOBS_PENDING

from .document_repo import DocumentRepository
from .exceptions import RecordNotFoundError
from .utils import update_record


class JobRepository:
    @staticmethod
    async def create(session: AsyncSession, *, job: JobCreate) -> JobRecord:
        if not await DocumentRepository.exists(session, document_id=job.document_id):
            raise RecordNotFoundError(f'Document {job.document_id} not found')

        access_ctx = AccessContext.from_session(session)
        proposed_metadata = job.proposed_metadata.model_dump(mode='json') if job.proposed_metadata else None

        record = JobRecord(
            created_by=access_ctx.user_id,
            tenant_id=access_ctx.tenant_id,
            status=job.status.value,
            percent=job.percent,
            step=job.step,
            proposed_metadata=proposed_metadata,
            document_id=job.document_id,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        session.add(record)
        try:
            await session.commit()
        except Exception as e:
            await session.rollback()
            raise Exception(f'Failed to create job: {e}')
        return record

    @staticmethod
    async def get(session: AsyncSession, *, job_id: UUID, refresh: bool = False) -> JobRecord:
        """Fetch a job by ID and eagerly load related entities (document, ingestion) without type issues."""
        stmt = select(JobRecord).where(JobRecord.id == job_id).execution_options(populate_existing=refresh)
        result = await session.exec(stmt)
        job = result.one_or_none()

        if job is None:
            raise RecordNotFoundError(f'Job {job_id} not found')

        await session.refresh(job, attribute_names=['document', 'ingestion'])
        return job

    @staticmethod
    async def update(session: AsyncSession, *, job: JobUpdate) -> JobRecord:
        record = await JobRepository.get(session, job_id=job.id)
        record = await update_record(record, data=job)

        try:
            await session.commit()
            await session.refresh(record)
        except Exception as e:
            await session.rollback()
            logger.error(f'Failed to update progress for job {job.id}: {e}')
        return record

    @staticmethod
    async def delete(session: AsyncSession, *, job_id: UUID) -> bool:
        # todo: also delete embeddings
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
    async def get_for_fingerprint(session: AsyncSession, *, document_id: UUID, fingerprint: str) -> JobRecord | None:
        stmt = (
            select(JobRecord)
            .join(IngestionRecord, onclause=JobRecord.id == IngestionRecord.job_id)
            .where(
                JobRecord.document_id == document_id,
                IngestionRecord.fingerprint == fingerprint,
            )
        )
        result = await session.exec(stmt)
        rows = result.all()

        if not rows:
            return None
        if len(rows) > 1:
            raise ValueError('Multiple JobRecords found for document and ingestion key; expected at most one.')
        return rows[0]

    @staticmethod
    async def get_active_for_document(session: AsyncSession, *, document_id: UUID) -> JobRecord | None:
        statuses = [s.value for s in JOBS_PENDING]
        stmt = select(JobRecord).where(
            JobRecord.document_id == document_id,
            or_(
                JobRecord.status == statuses[0],
                JobRecord.status == statuses[1],
            ),
        )
        res = await session.exec(stmt)
        return res.first()

    @staticmethod
    async def exists(session: AsyncSession, *, job_id: UUID) -> bool:
        try:
            return await session.get(JobRecord, job_id) is not None
        except RecordNotFoundError:
            return False
