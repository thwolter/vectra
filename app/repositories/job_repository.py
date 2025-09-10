"""
Repository for upload job status persistence.

Follows the style of MetadataRepository: lightweight explicit SQL for unit-testability,
backed by SQLModel table defined in repositories.models (created via DatabaseManager.ensure_schema()).
"""

from __future__ import annotations

from typing import Any, Optional
from datetime import datetime, timezone
from uuid import UUID

from loguru import logger
from sqlalchemy import text

from app.metadata.schemas import ProposedMetadata
from app.schemas.jobs import CreateJob, JobDocumentRefs
from app.schemas.upload import JobStatus, JobStatusResponse, JobProgress


class JobRepository:
    def __init__(self, db_manager: Any):
        self.db_manager = db_manager

    async def _ensure_db(self) -> None:
        if not self.db_manager.is_initialized:
            await self.db_manager.initialize()

    async def ensure_jobs_table(self) -> None:
        """Ensure the upload_jobs table exists and has required columns.

        We allow tests to run without explicit Alembic by adding new columns if they are missing.
        """
        await self._ensure_db()
        await self.db_manager.ensure_schema()
        # Add linkage and descriptive columns if they don't exist (idempotent)
        ddl = (
            'ALTER TABLE IF EXISTS upload_jobs '
            'ADD COLUMN IF NOT EXISTS digest TEXT, '
            'ADD COLUMN IF NOT EXISTS document_uuid UUID, '
            'ADD COLUMN IF NOT EXISTS collection TEXT, '
            'ADD COLUMN IF NOT EXISTS original_filename TEXT, '
            'ADD COLUMN IF NOT EXISTS content_type TEXT, '
            'ADD COLUMN IF NOT EXISTS size_bytes BIGINT, '
            'ADD COLUMN IF NOT EXISTS proposed_metadata JSONB'
        )
        idx_hex = (
            'CREATE INDEX IF NOT EXISTS ix_upload_jobs_digest ON upload_jobs(digest)'
        )
        idx_doc = 'CREATE INDEX IF NOT EXISTS ix_upload_jobs_document_uuid ON upload_jobs(document_uuid)'
        idx_coll = 'CREATE INDEX IF NOT EXISTS ix_upload_jobs_collection ON upload_jobs(collection)'
        # Add FK to documents(id), ON DELETE SET NULL (idempotent via constraint name)
        fk = (
            'ALTER TABLE IF EXISTS upload_jobs '
            'ADD CONSTRAINT IF NOT EXISTS fk_upload_jobs_document_uuid '
            'FOREIGN KEY (document_uuid) REFERENCES documents(id) ON DELETE SET NULL'
        )
        async with self.db_manager.get_session() as session:
            try:
                await session.execute(text(ddl))
                await session.execute(text(idx_hex))
                await session.execute(text(idx_doc))
                await session.execute(text(idx_coll))
                await session.execute(text(fk))
                # Avoid extra commits during unit tests; DDL is idempotent and often autocommitted
            except Exception:
                # Swallow errors here; table may not exist yet for some tests; ensured later on first insert
                pass

    @staticmethod
    def _serialize_proposed(proposed: Optional[dict]) -> str | None:
        if proposed is None:
            return None
        return __import__('json').dumps(proposed)

    @staticmethod
    def _deserialize_proposed(raw: str | None) -> Optional[dict]:
        if not raw:
            return None
        return __import__('json').loads(raw)

    async def create_job(self, *, job: CreateJob) -> None:
        """Insert a new job row using the CreateJob schema only.
        Legacy kwargs are removed to keep the codebase clean and forward-only.
        """
        await self.ensure_jobs_table()

        sql = (
            'INSERT INTO upload_jobs (job_id, status, percent, step, proposed_metadata, created_at, updated_at, '
            'digest, document_uuid, collection, original_filename, content_type, size_bytes) '
            'VALUES (:job_id, :status, :percent, :step, NULL, :created_at, :updated_at, '
            ':digest, :document_uuid, :collection, :original_filename, :content_type, :size_bytes) '
            'ON CONFLICT (job_id) DO NOTHING'
        )
        now_utc = datetime.now(timezone.utc)

        logger.debug(
            f'Creating job {job.job_id} with status {job.status}, percent {job.percent}, step {job.step}'
        )
        params = {
            'job_id': job.job_id,
            'status': job.status,
            'percent': job.percent,
            'step': job.step,
            'created_at': now_utc,
            'updated_at': now_utc,
            'document_uuid': job.document_uuid,
            'collection': job.collection,
            'digest': job.digest,
            'original_filename': job.original_filename,
            'content_type': job.content_type,
            'size_bytes': job.size_bytes,
        }

        pm_to_store = None
        if job.proposed_metadata is not None:
            pm_to_store = job.proposed_metadata.model_dump()

        async with self.db_manager.get_session() as session:
            try:
                await session.execute(text(sql), params)
                # If proposed provided, update via ORM so JSONB typing is handled
                if pm_to_store is not None:
                    try:
                        import json as _json

                        pm_str = _json.dumps(pm_to_store)
                    except Exception:
                        pm_str = None
                    if pm_str is not None:
                        upd_sql = text(
                            'UPDATE upload_jobs SET proposed_metadata = (:pm)::jsonb, updated_at = :updated_at WHERE job_id = :job_id'
                        )
                        await session.execute(
                            upd_sql,
                            {
                                'pm': pm_str,
                                'updated_at': datetime.now(timezone.utc),
                                'job_id': job.job_id,
                            },
                        )
                await session.commit()

            except Exception as e:
                await session.rollback()
                raise Exception(f'Failed to create job {job.job_id}: {e}')

    async def update_progress(
        self, *, job_id: UUID, percent: int, step: str | None
    ) -> None:
        await self._ensure_db()
        sql = (
            'UPDATE upload_jobs SET percent = :percent, step = :step, updated_at = :updated_at '
            'WHERE job_id = :job_id'
        )
        params = {
            'percent': percent,
            'step': step,
            'updated_at': datetime.now(timezone.utc),
            'job_id': job_id,
        }

        async with self.db_manager.get_session() as session:
            try:
                await session.execute(text(sql), params)
                await session.commit()
            except Exception as e:
                await session.rollback()
                logger.error(f'Failed to update progress for job {job_id}: {e}')

    async def update_status(
        self,
        *,
        job_id: UUID,
        status: JobStatus,
        proposed_metadata: ProposedMetadata | None = None,
        percent: int | None = None,
        step: str | None = None,
    ) -> None:
        await self._ensure_db()
        set_clauses = ['status = :status', 'updated_at = :updated_at']
        params: dict[str, Any] = {
            'status': status.value if hasattr(status, 'value') else str(status),
            'updated_at': datetime.now(timezone.utc),
            'job_id': job_id,
        }
        if percent is not None:
            set_clauses.append('percent = :percent')
            params['percent'] = percent
        if step is not None:
            set_clauses.append('step = :step')
            params['step'] = step
        if proposed_metadata is not None:
            # ProposedMetadata is guaranteed; serialize to dict for JSONB
            set_clauses.append('proposed_metadata = (:pm)::jsonb')
            import json as _json

            params['pm'] = _json.dumps(proposed_metadata.model_dump())
        base_sql = 'UPDATE upload_jobs SET ' + ', '.join(set_clauses)
        sql = base_sql + ' WHERE job_id = :job_id'

        async with self.db_manager.get_session() as session:
            try:
                await session.execute(text(sql), params)
                await session.commit()
            except Exception as e:
                await session.rollback()
                raise Exception(f'Failed to update status for job {job_id}: {e}')

    async def finalize(self, *, job_id: UUID, status=JobStatus.COMPLETED) -> None:
        # Single atomic update for finalization
        await self.update_status(job_id=job_id, status=status, percent=100, step='')

    async def get_status(self, *, job_id: UUID) -> JobStatusResponse | None:
        await self.ensure_jobs_table()
        async with self.db_manager.get_session() as session:
            sql = (
                'SELECT job_id, status, percent, step, original_filename, proposed_metadata, warnings, errors '
                'FROM upload_jobs WHERE job_id = :job_id LIMIT 1'
            )
            result = await session.execute(text(sql), {'job_id': job_id})
            row = result.mappings().first()
        if not row:
            return None
        data = dict(row)
        data.update(
            {
                'progress': JobProgress(**row),
                'warnings': row.warnings or [],
                'errors': row.errors or [],
            }
        )
        return JobStatusResponse(**data)

    async def get_job_document_refs(self, *, job_id: UUID) -> JobDocumentRefs | None:
        """
        Return a dictionary containing at least digest and collection for a job.
        Used by services to apply updates correlated to the job's document.
        """
        await self._ensure_db()
        async with self.db_manager.get_session() as session:
            sql = 'SELECT digest, collection, document_uuid FROM upload_jobs WHERE job_id = :job_id LIMIT 1'
            result = await session.execute(text(sql), {'job_id': job_id})
            row = result.mappings().first()
        if not row:
            return None
        return JobDocumentRefs(**row)

    async def delete(self, *, job_id: UUID) -> bool:
        """Delete a job by job_id.

        Uses DELETE ... RETURNING to determine if a row was removed.
        Returns True if a row was deleted; False otherwise.
        """
        # Only ensure DB manager is initialized; avoid DDL executes that pollute unit tests
        await self._ensure_db()
        sql = 'DELETE FROM upload_jobs WHERE job_id = :job_id RETURNING job_id'
        async with self.db_manager.get_session() as session:
            try:
                res = await session.execute(text(sql), {'job_id': job_id})
                row = res.fetchone() if hasattr(res, 'fetchone') else None
                await session.commit()
                return bool(row)
            except Exception as e:
                await session.rollback()
                logger.error(f'Failed to delete job {job_id}: {e}')
                return False

    def __repr__(self) -> str:
        return f'<JobRepository db_manager={self.db_manager}>'

    def __str__(self) -> str:
        return f'JobRepository(db_manager={self.db_manager})'
