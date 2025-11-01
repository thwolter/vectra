from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, cast
from uuid import UUID

from loguru import logger
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from tenauth.schemas import AccessContext

from repositories.models import IngestionRecord, JobRecord
from repositories.schemas import JobCreate, JobUpdate
from schemas.upload import JOBS_PENDING

from .document_repo import DocumentRepository, document_repository
from .exceptions import RecordNotFoundError
from .utils import update_record

if TYPE_CHECKING:
    from repositories.schemas import IngestionVersion


class JobRepository:
    """Persistence helpers for job records."""

    def __init__(self, document_repo: DocumentRepository | None = None) -> None:
        self._documents = document_repo or document_repository

    async def create(self, session: AsyncSession, *, job: JobCreate) -> JobRecord:
        if not await self._documents.exists(session, document_id=job.document_id):
            raise RecordNotFoundError(f'Document {job.document_id} not found')

        access_ctx = AccessContext.from_session(session)
        record = JobRecord(
            created_by=access_ctx.user_id,
            tenant_id=access_ctx.tenant_id,
            status=job.status.value,
            percent=job.percent,
            step=job.step,
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

    async def get(self, session: AsyncSession, *, job_id: UUID, refresh: bool = False) -> JobRecord:
        """Fetch a job by ID and eagerly load related entities (document, ingestion) without type issues."""
        stmt = select(JobRecord).where(JobRecord.id == job_id).execution_options(populate_existing=refresh)
        result = await session.exec(stmt)
        job = result.one_or_none()

        if job is None:
            raise RecordNotFoundError(f'Job {job_id} not found')

        await session.refresh(job, attribute_names=['document', 'ingestion'])
        return job

    async def update(self, session: AsyncSession, *, job: JobUpdate) -> JobRecord:
        record = await self.get(session, job_id=job.id)
        record = await update_record(record, data=job)

        try:
            await session.commit()
            await session.refresh(record)
        except Exception as e:
            await session.rollback()
            logger.error(f'Failed to update progress for job {job.id}: {e}')
        return record

    async def delete(self, session: AsyncSession, *, job_id: UUID) -> bool:
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

    async def get_for_version(
        self,
        session: AsyncSession,
        *,
        document_id: UUID,
        version: 'IngestionVersion',
    ) -> JobRecord | None:
        stmt = (
            select(JobRecord)
            .join(IngestionRecord, IngestionRecord.job_id == JobRecord.id)  # type: ignore[bad-argument-type]
            .where(
                JobRecord.document_id == document_id,
                IngestionRecord.parser_fp == version.parser_fp,
                IngestionRecord.chunker_fp == version.chunker_fp,
                IngestionRecord.embedding_fp == version.embedding_fp,
            )
        )
        result = await session.exec(stmt)
        rows = result.all()

        if not rows:
            return None
        if len(rows) > 1:
            raise ValueError('Multiple JobRecords found for document and ingestion key; expected at most one.')
        return rows[0]

    async def get_active_for_document(self, session: AsyncSession, *, document_id: UUID) -> JobRecord | None:
        statuses = [s.value for s in JOBS_PENDING]
        stmt = select(JobRecord).where(
            JobRecord.document_id == document_id,
            cast(Any, JobRecord.status).in_(tuple(statuses)),
        )
        res = await session.exec(stmt)
        return res.first()

    async def exists(self, session: AsyncSession, *, job_id: UUID) -> bool:
        try:
            return await session.get(JobRecord, job_id) is not None
        except RecordNotFoundError:
            return False


job_repository = JobRepository()
