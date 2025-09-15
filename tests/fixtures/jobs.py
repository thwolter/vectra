from typing import AsyncGenerator
from uuid import UUID, uuid4

import pytest

from app.services.job_service import JobService
from app.metadata.schemas import ProposedMetadata
from app.schemas.jobs import InitJob
from app.schemas.enums import CollectionEnum


@pytest.fixture
async def job_created(session, digest_random) -> AsyncGenerator[UUID, None]:
    """Create a job row in the database; yields job_id and cleans up after."""
    job_service = JobService()
    proposed = ProposedMetadata(
        metadata={
            'company': 'ACME Inc.',
            'financial_year': 2024,
            'document_type': '10-Q',
        },
        confidence={},
        conflicts=[],
    )

    job = InitJob(
        document_uuid=uuid4(),
        collection=CollectionEnum.DEFAULT.value,
        digest=digest_random,
        original_filename='test_file_name.pdf',
        content_type='application/pdf',
        size_bytes=1024,
        proposed_metadata=proposed,
    )
    job_id = await job_service.init_job(session, job=job)
    try:
        yield job_id
    finally:
        await job_service.delete_job(session, job_id=job_id)
