import pytest

from repositories import job_repository
from repositories.exceptions import RecordNotFoundError
from repositories.schemas import IngestionVersion, JobCreate, JobUpdate
from schemas.upload import JobStatus


@pytest.mark.needs_postgres
async def test_can_create_job(auth_session, job_created):
    result = await job_repository.get(auth_session, job_id=job_created.id)
    assert result is not None
    assert result.id == job_created.id


@pytest.mark.needs_postgres
async def test_can_create_another_job_for_document(auth_session, job_created):
    new_job = JobCreate.model_validate(job_created.model_dump())
    # When the existing job is completed, we can create another one. To avoid changing the existing jog, let's
    # Let's create a completed job despite avoiding changing the existing one.
    new_job.status = JobStatus.COMPLETED
    job = await job_repository.create(auth_session, job=new_job)
    assert job.id is not None
    assert job.id != job_created.id
    auth_session.delete(job)


@pytest.mark.needs_postgres
async def test_can_delete_job(auth_session, job_created):
    deleted = await job_repository.delete(auth_session, job_id=job_created.id)
    assert deleted is True

    with pytest.raises(RecordNotFoundError):
        await job_repository.get(auth_session, job_id=job_created.id)

    # Second delete is a no-op
    second = await job_repository.delete(auth_session, job_id=job_created.id)
    assert second is False


@pytest.mark.needs_postgres
async def test_can_update_job(auth_session, job_created):
    job = JobUpdate.model_validate(job_created)
    job.status = JobStatus.NEEDS_REVIEW
    job.percent = 100
    job.step = 'review'
    updated_job = await job_repository.update(auth_session, job=job)
    assert updated_job.id == job_created.id
    assert updated_job.status == JobStatus.NEEDS_REVIEW.value
    assert updated_job.percent == 100
    assert updated_job.step == 'review'


@pytest.mark.needs_postgres
async def test_correctly_sets_timestamps(auth_session, job_created):
    created_at = job_created.created_at
    job = JobUpdate.model_validate(job_created)
    updated_job = await job_repository.update(auth_session, job=job)
    assert updated_job.created_at == created_at
    assert updated_job.created_at == created_at
    assert updated_job.updated_at > created_at


@pytest.mark.needs_postgres
async def test_correctly_sets_users(job_created, session_another_user):
    created_by = job_created.created_by
    job = JobUpdate.model_validate(job_created)

    job.percent = (job.percent or 0) + 1
    updated_job = await job_repository.update(session_another_user, job=job)
    assert updated_job.created_by == created_by
    assert updated_job.updated_by == session_another_user.info['user_id']


@pytest.mark.needs_postgres
async def test_get_for_version(auth_session, ingestion_created):
    document_id = ingestion_created.document_id
    version = IngestionVersion(
        collection=ingestion_created.collection,
        parser_fp=ingestion_created.parser_fp,
        chunker_fp=ingestion_created.chunker_fp,
        embedding_fp=ingestion_created.embedding_fp,
    )
    job = await job_repository.get_for_version(auth_session, document_id=document_id, version=version)
    assert job is not None

    mismatch_version = version.model_copy(update={'embedding_fp': 'different'})
    job2 = await job_repository.get_for_version(auth_session, document_id=document_id, version=mismatch_version)
    assert job2 is None
