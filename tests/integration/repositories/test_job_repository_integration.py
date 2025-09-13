import uuid

import pytest

from app.repositories import Job
from app.schemas.upload import JobStatus
from app.schemas.enums import CollectionEnum
from app.repositories.schemas import CreateJobCmd
from app.repositories.exceptions import JobNotFoundError


@pytest.mark.integration
@pytest.mark.needs_postgres
@pytest.mark.asyncio
async def test_delete_job_removes_row_and_is_idempotent(
    session,
    random_digest,
):
    document_uuid = uuid.uuid4()

    # Create a job
    job = CreateJobCmd(
        document_uuid=document_uuid,
        collection=CollectionEnum.DEFAULT.value,
        digest=random_digest,
        original_filename='upload.pdf',
        content_type='application/pdf',
        size_bytes=123,
        status=JobStatus.PROCESSING,
        percent=0,
        step='init',
    )
    job_id, _ = await Job.upsert(session, job=job)

    # Ensure it exists
    status = await Job.status(session, job_id=job_id)
    assert status is not None
    assert status.job_id == job_id

    # Delete the job
    first = await Job.delete(session, job_id=job_id)
    assert first is True

    with pytest.raises(JobNotFoundError):
        await Job.status(session, job_id=job_id)

    # Second delete is a no-op
    second = await Job.delete(session, job_id=job_id)
    assert second is False


@pytest.mark.integration
@pytest.mark.needs_postgres
@pytest.mark.asyncio
async def test_update_status(session, random_digest):
    document_uuid = uuid.uuid4()

    job = CreateJobCmd(
        document_uuid=document_uuid,
        collection=CollectionEnum.DEFAULT.value,
        digest=random_digest,
        original_filename='file.txt',
        content_type='text/plain',
        size_bytes=10,
        status=JobStatus.PROCESSING,
        percent=5,
        step='hash',
    )
    job_id, _ = await Job.upsert(session, job=job)

    # Update status to COMPLETED with percent/step overrides
    await Job.update_status(
        session,
        job_id=job_id,
        status=JobStatus.COMPLETED,
        percent=100,
        step='done',
    )

    status = await Job.status(session, job_id=job_id)
    assert status is not None
    assert status.status == JobStatus.COMPLETED
    assert status.progress.percent == 100
    assert status.progress.step == 'done'


@pytest.mark.integration
@pytest.mark.needs_postgres
@pytest.mark.asyncio
async def test_update_progress(session, random_digest):
    document_uuid = uuid.uuid4()

    job = CreateJobCmd(
        document_uuid=document_uuid,
        collection=CollectionEnum.DEFAULT.value,
        digest=random_digest,
        original_filename='file.txt',
        content_type='text/plain',
        size_bytes=10,
        status=JobStatus.PROCESSING,
        percent=0,
        step='start',
    )
    job_id, _ = await Job.upsert(session, job=job)

    await Job.update_progress(session, job_id=job_id, percent=42, step='parsing')

    status = await Job.status(session, job_id=job_id)
    assert status is not None
    assert status.status == JobStatus.PROCESSING
    assert status.progress.percent == 42
    assert status.progress.step == 'parsing'


@pytest.mark.integration
@pytest.mark.needs_postgres
@pytest.mark.asyncio
async def test_job_document_refs(session, random_digest):
    document_uuid = uuid.uuid4()

    job = CreateJobCmd(
        document_uuid=document_uuid,
        collection=CollectionEnum.DEFAULT.value,
        digest=random_digest,
        original_filename='report.pdf',
        content_type='application/pdf',
        size_bytes=2048,
        status=JobStatus.PROCESSING,
        percent=1,
        step='queued',
    )
    job_id, _ = await Job.upsert(session, job=job)

    refs = await Job.document_refs(session, job_id=job_id)
    assert refs is not None
    assert refs.digest == random_digest
    assert refs.collection == CollectionEnum.DEFAULT.value
    assert refs.document_uuid == document_uuid
