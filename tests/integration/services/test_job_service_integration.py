import uuid

import pytest

from app.services.job_service import JobService
from app.schemas.upload import JobStatus
from app.schemas.jobs import InitJob


@pytest.mark.integration
@pytest.mark.needs_postgres
@pytest.mark.asyncio
async def test_job_service_lifecycle_persists_in_db(digest_random, session):
    service = JobService()

    init_job = InitJob(
        digest=digest_random,
        document_uuid=uuid.uuid4(),
        collection='default',
        original_filename='file.pdf',
        content_type='application/pdf',
        size_bytes=42,
    )
    job_id = await service.init_job(session, job=init_job)

    # After init, status should be processing/0/hash
    status = await service.get_status(session, job_id=job_id)
    assert status.job_id == job_id
    assert status.status == JobStatus.PROCESSING
    assert status.progress.percent == 0

    # Update progress monotonically
    await service.update_progress(session, job_id=job_id, percent=50, step='parse')
    await service.update_progress(
        session, job_id=job_id, percent=10, step=''
    )  # should remain 50 and step None

    st2 = await service.get_status(session=session, job_id=job_id)
    assert st2.progress.percent >= 50

    # Valid transitions: processing -> needs_review -> completed
    await service.update_status(
        session,
        job_id=job_id,
        status=JobStatus.NEEDS_REVIEW,
        percent=80,
        step='extract-meta',
    )
    st3 = await service.get_status(session=session, job_id=job_id)
    assert st3.status == JobStatus.NEEDS_REVIEW

    await service.update_status(
        session, job_id=job_id, status=JobStatus.COMPLETED, percent=100, step='finalize'
    )
    st4 = await service.get_status(session=session, job_id=job_id)
    assert st4.status == JobStatus.COMPLETED
    assert st4.progress.percent == 100


@pytest.mark.integration
@pytest.mark.needs_postgres
@pytest.mark.asyncio
async def test_invalid_transition_after_completed_raises_and_state_stays_completed(
    digest_random, session
):
    service = JobService()

    from app.schemas.jobs import InitJob

    init = InitJob(
        digest=digest_random,
        document_uuid=uuid.uuid4(),
        collection='default',
        original_filename='file2.pdf',
        content_type='application/pdf',
        size_bytes=100,
    )
    job_id = await service.init_job(session, job=init)

    await service.update_status(
        session, job_id=job_id, status=JobStatus.COMPLETED, percent=100, step=''
    )

    with pytest.raises(ValueError):
        await service.update_status(session, job_id=job_id, status=JobStatus.PROCESSING)

    final = await service.get_status(session=session, job_id=job_id)
    assert final.status == JobStatus.COMPLETED
