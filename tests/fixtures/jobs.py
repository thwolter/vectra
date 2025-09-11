from typing import AsyncGenerator
from uuid import UUID, uuid4

import pytest

from app.services.job_service import JobService
from app.metadata.schemas import ProposedMetadata
from app.schemas.jobs import InitJob
from app.schemas.enums import CollectionEnum


@pytest.fixture
async def created_job_id(session, random_digest) -> AsyncGenerator[UUID, None]:
    """Create a job row in the database with proposed metadata."""
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
        digest=random_digest,
        original_filename='test_file_name.pdf',
        content_type='application/pdf',
        size_bytes=1024,
        proposed_metadata=proposed,
    )
    job_id = await job_service.init_job(session, job=job)
    yield job_id
    await job_service.delete_job(session, job_id=job_id)
