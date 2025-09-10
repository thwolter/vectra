import base64
import os
import uuid

import pytest

from app.core.dependencies import get_database_manager
from app.repositories.job_repository import JobRepository
from app.schemas.jobs import CreateJob
from app.schemas.upload import JobStatus
from app.schemas.enums import CollectionEnum


@pytest.fixture
async def repo() -> JobRepository:
    return JobRepository(get_database_manager())


def _random_sha256_b64() -> str:
    # 32 bytes -> standard base64 with '=' padding => 44 chars
    return base64.b64encode(os.urandom(32)).decode('ascii')


@pytest.mark.integration
@pytest.mark.needs_postgres
@pytest.mark.asyncio
async def test_delete_job_removes_row_and_is_idempotent(repo: JobRepository):
    job_id = uuid.uuid4()
    document_uuid = uuid.uuid4()
    digest = _random_sha256_b64()

    # Create a job
    job = CreateJob(
        job_id=job_id,
        document_uuid=document_uuid,
        collection=CollectionEnum.DEFAULT.value,
        digest=digest,
        original_filename='upload.pdf',
        content_type='application/pdf',
        size_bytes=123,
        status=JobStatus.PROCESSING.value,
        percent=0,
        step='init',
    )
    await repo.create_job(job=job)

    # Ensure it exists
    status = await repo.get_status(job_id=job_id)
    assert status is not None
    assert status.job_id == job_id

    # Delete the job
    first = await repo.delete(job_id=job_id)
    assert first is True
    # Verify it's gone
    status_after = await repo.get_status(job_id=job_id)
    assert status_after is None

    # Second delete is a no-op
    second = await repo.delete(job_id=job_id)
    assert second is False
