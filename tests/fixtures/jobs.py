from typing import AsyncGenerator

import pytest

from repositories import job_repository
from repositories.models import JobRecord
from repositories.schemas import JobCreate
from schemas.upload import JobStatus


@pytest.fixture
async def job_created(auth_session, document_created) -> AsyncGenerator[JobRecord, None]:
    job_create = JobCreate(
        document_id=document_created.id,
        status=JobStatus.PROCESSING,
        percent=0,
        step='init',
    )

    job = await job_repository.create(auth_session, job=job_create)
    job_id = job.id
    yield job
    await job_repository.delete(auth_session, job_id=job_id)
