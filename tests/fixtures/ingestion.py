import pytest

from app.repositories import ingestion_repository, job_repository
from app.repositories.schemas import IngestionCreate, JobUpdate
from app.schemas.upload import JobStatus
from app.services.job_service import JobService


@pytest.fixture
async def ingestion_created(session, job_created, digest_random):
    ingestion_create = IngestionCreate.create(
        collection='default', document_id=job_created.document_id, job_id=job_created.id, digest=digest_random
    )
    record = await ingestion_repository.create(session, data=ingestion_create)
    await job_repository.update(session, job=JobUpdate(id=job_created.id, status=JobStatus.NEEDS_REVIEW))
    await JobService().ingestion_created(session, job_id=job_created.id, ingestion=record)
    yield record
    await session.delete(record)


@pytest.fixture
async def ingestion_created_with_review(session, job_created, digest_random):
    ingestion_create = IngestionCreate.create(
        collection='default', document_id=job_created.document_id, job_id=job_created.id, digest=digest_random
    )
    record = await ingestion_repository.create(session, data=ingestion_create)
    await job_repository.update(session, job=JobUpdate(id=job_created.id, status=JobStatus.NEEDS_REVIEW))
    await JobService().ingestion_created(session, job_id=job_created.id, ingestion=record)
    yield record
    await session.delete(record)


@pytest.fixture
async def ingestion_created_with_completed(session, job_created, digest_random):
    ingestion_create = IngestionCreate.create(
        collection='default', document_id=job_created.document_id, job_id=job_created.id, digest=digest_random
    )
    record = await ingestion_repository.create(session, data=ingestion_create)
    await job_repository.update(session, job=JobUpdate(id=job_created.id, status=JobStatus.COMPLETED))
    await JobService().ingestion_created(session, job_id=job_created.id, ingestion=record)
    yield record
    await session.delete(record)
