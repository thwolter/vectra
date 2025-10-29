import pytest

from schemas.upload import JobStatus
from services.job_service import JobService


async def test_job_service_lifecycle_persists_in_db(digest_random, auth_session, job_created):
    service = JobService()
    job_id = job_created.id

    # After init, status should be processing/0/hash
    status = await service.get_status(auth_session, job_id=job_id)
    assert status.job_id == job_id
    assert status.status == JobStatus.PROCESSING
    assert status.progress.percent == 0

    # Update progress monotonically
    await service.update_progress(auth_session, job_id=job_id, percent=50, step='parse')
    await service.update_progress(auth_session, job_id=job_id, percent=10, step='')  # should remain 50 and step None

    st2 = await service.get_status(session=auth_session, job_id=job_id)
    assert st2.progress.percent >= 50

    # Valid transitions: processing -> completed
    await service.update_status(auth_session, job_id=job_id, status=JobStatus.COMPLETED, percent=100, step='finalize')
    st4 = await service.get_status(session=auth_session, job_id=job_id)
    assert st4.status == JobStatus.COMPLETED
    assert st4.progress.percent == 100


@pytest.mark.needs_postgres
async def test_invalid_transition_after_completed_raises_and_state_stays_completed(
    digest_random, auth_session, job_created
):
    service = JobService()

    await service.update_status(auth_session, job_id=job_created.id, status=JobStatus.COMPLETED, percent=100, step='')

    with pytest.raises(ValueError):
        await service.update_status(auth_session, job_id=job_created.id, status=JobStatus.PROCESSING)

    final = await service.get_status(session=auth_session, job_id=job_created.id)
    assert final.status == JobStatus.COMPLETED
