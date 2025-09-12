from __future__ import annotations

from typing import Any
from datetime import datetime, timezone
from uuid import UUID, uuid4
import json

from loguru import logger
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.metadata.schemas import ProposedMetadata
from app.schemas.upload import JobStatus
from app.repositories.schemas import (
    CreateJobCmd,
    JobDocumentRefs,
    JobStatusSnapshot,
    JobProgressSnapshot,
)


class Job:
    @staticmethod
    async def create(session: AsyncSession, *, job: CreateJobCmd) -> UUID:
        logger.debug(
            f'Creating job with status {job.status}, percent {job.percent}, step {job.step}'
        )
        sql = (
            'INSERT INTO upload_jobs ('
            ' id, tenant_id, created_by, status, percent, step, proposed_metadata, created_at, '
            ' digest, document_uuid, collection, original_filename, content_type, size_bytes'
            ' ) VALUES ('
            " :id, current_setting('app.tenant_id', true)::uuid, :created_by, :status, :percent, :step, "
            " (:pm)::jsonb, timezone('utc', now()), :digest, :document_uuid, :collection, :original_filename, "
            ' :content_type, :size_bytes'
            ') RETURNING id'
        )
        params = {
            'id': uuid4(),
            'created_by': session.info.user_id,
            'status': job.status.value
            if hasattr(job.status, 'value')
            else str(job.status),
            'percent': job.percent,
            'step': job.step,
            'document_uuid': job.document_uuid,
            'collection': job.collection,
            'digest': job.digest,
            'original_filename': job.original_filename,
            'content_type': job.content_type,
            'size_bytes': job.size_bytes,
            'pm': (
                job.proposed_metadata.model_dump_json()
                if job.proposed_metadata is not None
                else None
            ),
        }
        try:
            res = await session.execute(text(sql), params)
            row = res.fetchone()
            await session.commit()
        except Exception as e:
            await session.rollback()
            raise Exception(f'Failed to create job: {e}')
        if not row:
            raise RuntimeError('Insert into upload_jobs did not return an id')
        return row[0]

    @staticmethod
    async def update_progress(
        session: AsyncSession,
        *,
        job_id: UUID,
        percent: int,
        step: str | None,
    ) -> None:
        sql = (
            'UPDATE upload_jobs SET percent = :percent, step = :step, updated_at = :updated_at '
            'WHERE id = :id'
        )
        params = {
            'percent': percent,
            'step': step,
            'updated_at': datetime.now(timezone.utc),
            'id': job_id,
        }
        try:
            await session.execute(text(sql), params)
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
        set_clauses = ['status = :status', 'updated_at = :updated_at']
        params: dict[str, Any] = {
            'status': status.value if hasattr(status, 'value') else str(status),
            'updated_at': datetime.now(timezone.utc),
            'id': job_id,
        }
        if percent is not None:
            set_clauses.append('percent = :percent')
            params['percent'] = percent
        if step is not None:
            set_clauses.append('step = :step')
            params['step'] = step
        if proposed_metadata is not None:
            set_clauses.append('proposed_metadata = (:pm)::jsonb')
            params['pm'] = json.dumps(proposed_metadata.model_dump(mode='json'))
        base_sql = 'UPDATE upload_jobs SET ' + ', '.join(set_clauses)
        sql = base_sql + ' WHERE id = :id'

        try:
            await session.execute(text(sql), params)
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
        sql = (
            'SELECT id, status, percent, step, original_filename, proposed_metadata, warnings, errors '
            'FROM upload_jobs WHERE id = :id LIMIT 1'
        )
        result = await session.execute(text(sql), {'id': job_id})
        row = result.mappings().first()
        if not row:
            return None
        # Try to rehydrate ProposedMetadata if possible
        pm = row.proposed_metadata
        proposed = None
        if pm is not None:
            try:
                import json as _json

                if isinstance(pm, str):
                    pm = _json.loads(pm)
                if isinstance(pm, dict):
                    from app.metadata.schemas import ProposedMetadata as _PM

                    proposed = _PM(**pm)
            except Exception:
                proposed = None
        return JobStatusSnapshot(
            job_id=row.id,
            status=JobStatus(row.status)
            if not isinstance(row.status, JobStatus)
            else row.status,
            progress=JobProgressSnapshot(percent=row.percent or 0, step=row.step),
            original_filename=row.original_filename,
            proposed_metadata=proposed,
            warnings=row.warnings or [],
            errors=row.errors or [],
        )

    @staticmethod
    async def get_job_document_refs(
        session: AsyncSession, *, job_id: UUID
    ) -> JobDocumentRefs | None:
        """
        Return a dictionary containing at least digest and collection for a job.
        Used by services to apply updates correlated to the job's document.
        """
        sql = 'SELECT digest, collection, document_uuid FROM upload_jobs WHERE id = :id LIMIT 1'
        result = await session.execute(text(sql), {'id': job_id})
        row = result.mappings().first()
        if not row:
            return None
        return JobDocumentRefs(**dict(row))

    @staticmethod
    async def delete(session: AsyncSession, *, job_id: UUID) -> bool:
        """Delete a job by job_id.

        Uses DELETE ... RETURNING to determine if a row was removed.
        Returns True if a row was deleted; False otherwise.
        """
        sql = 'DELETE FROM upload_jobs WHERE id = :id RETURNING id'

        try:
            res = await session.execute(text(sql), {'id': job_id})
            row = res.fetchone() if hasattr(res, 'fetchone') else None
            await session.commit()
            return bool(row)
        except Exception as e:
            await session.rollback()
            logger.error(f'Failed to delete job {job_id}: {e}')
            return False
