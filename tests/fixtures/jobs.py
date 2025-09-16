from typing import AsyncGenerator

import pytest

from app.metadata.schemas import ProposedMetadata
from app.repositories import JobRepository
from app.repositories.models import JobRecord
from app.repositories.schemas import JobCreate
from app.schemas.upload import JobStatus


@pytest.fixture
async def job_created(session, document_created) -> AsyncGenerator[JobRecord, None]:
    job_create = JobCreate(
        document_id=document_created.id,
        status=JobStatus.PROCESSING,
        percent=0,
        step='init',
        proposed_metadata=ProposedMetadata(metadata={'company': 'ACME Inc.', 'document_type': '10-Q4'}),
    )

    job = await JobRepository.create(session, job=job_create)
    job_id = job.id
    yield job
    await JobRepository.delete(session, job_id=job_id)
