import pytest

from app.repositories import JobRepository
from app.repositories.exceptions import RecordNotFoundError
from app.repositories.schemas import JobCreate, JobUpdate
from app.schemas.upload import JobStatus


@pytest.mark.needs_postgres
async def test_can_create_job(session, job_created):
    result = await JobRepository.get(session, job_id=job_created.id)
    assert result is not None
    assert result.id == job_created.id


@pytest.mark.needs_postgres
async def test_can_create_another_job_for_document(session, job_created):
    new_job = JobCreate.model_validate(job_created.model_dump())
    # When the existing job is completed, we can create another one. To avoid changing the existing jog, let's
    # Let's create a completed job despite avoiding changing the existing one.
    new_job.status = JobStatus.COMPLETED
    job = await JobRepository.create(session, job=new_job)
    assert job.id is not None
    assert job.id != job_created.id
    session.delete(job)


@pytest.mark.needs_postgres
async def test_can_delete_job(session, job_created):
    deleted = await JobRepository.delete(session, job_id=job_created.id)
    assert deleted is True

    with pytest.raises(RecordNotFoundError):
        await JobRepository.get(session, job_id=job_created.id)

    # Second delete is a no-op
    second = await JobRepository.delete(session, job_id=job_created.id)
    assert second is False


@pytest.mark.needs_postgres
async def test_can_update_job(session, job_created):
    job = JobUpdate.model_validate(job_created)
    job.status = JobStatus.NEEDS_REVIEW
    job.percent = 100
    job.step = 'review'
    updated_job = await JobRepository.update(session, job=job)
    assert updated_job.id == job_created.id
    assert updated_job.status == JobStatus.NEEDS_REVIEW.value
    assert updated_job.percent == 100
    assert updated_job.step == 'review'


@pytest.mark.needs_postgres
async def test_correctly_sets_timestamps(session, job_created):
    created_at = job_created.created_at
    job = JobUpdate.model_validate(job_created)
    updated_job = await JobRepository.update(session, job=job)
    assert updated_job.created_at == created_at
    assert updated_job.created_at == created_at
    assert updated_job.updated_at > created_at


@pytest.mark.needs_postgres
async def test_correctly_sets_users(session, job_created, session_another_user):
    created_by = job_created.created_by
    job = JobUpdate.model_validate(job_created)

    job.percent = (job.percent or 0) + 1
    updated_job = await JobRepository.update(session_another_user, job=job)
    assert updated_job.created_by == created_by
    assert updated_job.updated_by == session_another_user.info['user_id']


@pytest.mark.needs_postgres
async def test_get_for_fingerprint(session, ingestion_created):
    document_id = ingestion_created.document_id
    fingerprint = ingestion_created.fingerprint
    job = await JobRepository.get_for_fingerprint(session, document_id=document_id, fingerprint=fingerprint)
    assert job is not None

    job2 = await JobRepository.get_for_fingerprint(session, document_id=document_id, fingerprint='foo')
    assert job2 is None
