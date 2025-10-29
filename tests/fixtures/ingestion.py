import pytest

from repositories import ingestion_repository, job_repository
from repositories.schemas import IngestionCreate, JobUpdate
from schemas.upload import JobStatus
from services.job_service import JobService


@pytest.fixture
async def ingestion_created(auth_session, job_created, digest_random):
    ingestion_create = IngestionCreate.create(
        collection='default', document_id=job_created.document_id, job_id=job_created.id, digest=digest_random
    )
    record = await ingestion_repository.create(auth_session, data=ingestion_create)
    await job_repository.update(auth_session, job=JobUpdate(id=job_created.id, status=JobStatus.NEEDS_REVIEW))
    await JobService().ingestion_created(auth_session, job_id=job_created.id, ingestion=record)
    yield record
    await auth_session.delete(record)


@pytest.fixture
async def ingestion_created_with_review(auth_session, job_created, digest_random):
    ingestion_create = IngestionCreate.create(
        collection='default', document_id=job_created.document_id, job_id=job_created.id, digest=digest_random
    )
    record = await ingestion_repository.create(auth_session, data=ingestion_create)
    await job_repository.update(auth_session, job=JobUpdate(id=job_created.id, status=JobStatus.NEEDS_REVIEW))
    await JobService().ingestion_created(auth_session, job_id=job_created.id, ingestion=record)
    yield record
    await auth_session.delete(record)


@pytest.fixture
async def ingestion_created_with_completed(auth_session, job_created, digest_random):
    ingestion_create = IngestionCreate.create(
        collection='default', document_id=job_created.document_id, job_id=job_created.id, digest=digest_random
    )
    record = await ingestion_repository.create(auth_session, data=ingestion_create)
    await job_repository.update(auth_session, job=JobUpdate(id=job_created.id, status=JobStatus.COMPLETED))
    await JobService().ingestion_created(auth_session, job_id=job_created.id, ingestion=record)
    yield record
    await auth_session.delete(record)
