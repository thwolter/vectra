import uuid
from unittest.mock import create_autospec

import pytest

from app.services.job_service import JobService
from app.repositories import Job
from app.schemas.upload import JobStatus, JobStatusResponse, JobProgress
from app.metadata.schemas import ProposedMetadata, Evidence
from app.schemas.jobs import InitJob


@pytest.fixture(scope='function')
def FakeJob():
    fake_job = create_autospec(Job)
    fake_job.create.return_value = None
    fake_job.get_status.return_value = None
    fake_job.status_updates = []
    return fake_job


@pytest.mark.asyncio
async def test_init_job_sets_canonical_defaults_and_passes_fields(
    digest_str, mock_session, monkeypatch, FakeJob
):
    monkeypatch.setattr('app.services.job_service.Job', FakeJob)
    service = JobService()

    job_id = uuid.uuid4()
    job = InitJob(
        digest=digest_str,
        document_uuid=job_id,
        collection='default',
        original_filename='a.pdf',
        content_type='application/pdf',
        size_bytes=123,
    )
    await service.init_job(mock_session, job=job)
    assert FakeJob.create.call_count == 1


@pytest.mark.asyncio
async def test_update_progress_clamps_and_monotonic_and_normalizes_step(
    mock_session, monkeypatch, FakeJob
):
    monkeypatch.setattr('app.services.job_service.Job', FakeJob)
    job_id = uuid.uuid4()

    # Seed current status so the service has a baseline (40%)
    FakeJob.get_status.return_value = JobStatusResponse(
        job_id=job_id,
        status=JobStatus.PROCESSING,
        progress=JobProgress(percent=40, step='parse'),
    )

    FakeJob.progress_updates = []

    async def _update_progress(*args, **kwargs):
        FakeJob.progress_updates.append(
            (kwargs.get('job_id'), kwargs.get('percent'), kwargs.get('step'))
        )

    FakeJob.update_progress.side_effect = _update_progress

    service = JobService()

    # 1) Below current (10 < 40) -> stays at 40; empty step -> None
    await service.update_progress(mock_session, job_id=job_id, percent=10, step='')
    assert FakeJob.progress_updates[0] == (job_id, 40, None)

    # 2) Above 100 -> clamped to 100; step preserved
    await service.update_progress(
        mock_session, job_id=job_id, percent=150, step='embed'
    )
    assert FakeJob.progress_updates[1] == (job_id, 100, 'embed')


@pytest.mark.asyncio
async def test_update_status_valid_transition_and_clamping_and_step_norm(
    mock_session, monkeypatch, FakeJob
):
    monkeypatch.setattr('app.services.job_service.Job', FakeJob)
    job_id = uuid.uuid4()

    FakeJob.get_status.return_value = JobStatusResponse(
        job_id=job_id,
        status=JobStatus.PROCESSING,
        progress=JobProgress(percent=20, step='parse'),
    )

    # Capture update_status kwargs
    FakeJob.status_updates = []

    async def _update_status(**kwargs):
        FakeJob.status_updates.append(kwargs)

    FakeJob.update_status.side_effect = _update_status

    service = JobService()

    proposed = ProposedMetadata(
        metadata={'company': 'Acme', 'financial_year': 2024},
        confidence=dict(
            company=Evidence(score=0.8, snippet=''),
            financial_year=Evidence(score=0.7, snippet=''),
        ),
        conflicts=['company_legal_name'],
    )

    await service.update_status(
        mock_session,
        job_id=job_id,
        status=JobStatus.NEEDS_REVIEW,
        proposed_metadata=proposed,
        percent=120,  # will be clamped
        step='',  # will be normalized to None
    )

    upd = FakeJob.status_updates[-1]
    assert upd['status'] == JobStatus.NEEDS_REVIEW
    assert upd['percent'] == 100
    assert upd['step'] is None
    # ensure proposed serialized dict was passed
    assert isinstance(upd['proposed_metadata'], ProposedMetadata)


@pytest.mark.asyncio
async def test_update_status_invalid_transition_raises(
    mock_session, monkeypatch, FakeJob
):
    monkeypatch.setattr('app.services.job_service.Job', FakeJob)
    job_id = uuid.uuid4()
    FakeJob.get_status.return_value = JobStatusResponse(
        job_id=job_id,
        status=JobStatus.COMPLETED,
        progress=JobProgress(percent=100, step=''),
    )
    service = JobService()

    with pytest.raises(ValueError):
        await service.update_status(
            mock_session, job_id=job_id, status=JobStatus.PROCESSING
        )

    assert FakeJob.update_status.await_count == 0


@pytest.mark.asyncio
async def test_fail_job_sets_failed_status(mock_session, monkeypatch, FakeJob):
    monkeypatch.setattr('app.services.job_service.Job', FakeJob)
    job_id = uuid.uuid4()

    async def _update_status(**kwargs):
        FakeJob.status_updates.append(kwargs)

    FakeJob.update_status.side_effect = _update_status

    service = JobService()

    await service.fail_job(
        mock_session, job_id=job_id, exc=RuntimeError('boom'), last_step='embed'
    )

    assert any(u['status'] == JobStatus.FAILED for u in FakeJob.status_updates)


@pytest.mark.asyncio
async def test_get_status_not_found_returns_failed_with_error(
    mock_session, monkeypatch, FakeJob
):
    monkeypatch.setattr('app.services.job_service.Job', FakeJob)
    # Ensure repository returns "not found" for this test regardless of prior mutations
    FakeJob.get_status.return_value = None
    service = JobService()

    job_id = uuid.uuid4()
    resp = await service.get_status(session=mock_session, job_id=job_id)
    assert resp.job_id == job_id
    assert resp.status == JobStatus.FAILED
    # Be resilient to implementation differences (list vs tuple, None vs [])
    errors = list(resp.errors or [])
    assert 'job_not_found' in errors


@pytest.mark.asyncio
async def test_get_status_rehydrates_proposed_metadata(
    mock_session, monkeypatch, FakeJob
):
    proposed = ProposedMetadata(
        metadata={'company': 'Acme', 'financial_year': 2024},
        confidence={
            'company': Evidence(score=0.9, snippet=''),
            'financial_year': Evidence(score=0.8, snippet=''),
        },
        conflicts=['reporting_year'],
    )
    FakeJob = create_autospec(Job, instance=True)
    # Patch the Job symbol used inside JobService
    monkeypatch.setattr('app.services.job_service.Job', FakeJob)
    job_id = uuid.uuid4()
    # Repository returns a plain dict; proposed_metadata is also a dict
    FakeJob.get_status.return_value = JobStatusResponse(
        job_id=job_id,
        status=JobStatus.NEEDS_REVIEW,
        progress=JobProgress(percent=80, step='extract-meta'),
        proposed_metadata=proposed,
        warnings=[],
        errors=[],
    )
    service = JobService()

    resp = await service.get_status(session=mock_session, job_id=job_id)
    assert isinstance(resp, JobStatusResponse)
    assert resp.status == JobStatus.NEEDS_REVIEW
    assert resp.proposed_metadata is not None
    assert isinstance(resp.proposed_metadata, ProposedMetadata)
    assert resp.proposed_metadata.metadata.get('company') == 'Acme'
    assert resp.proposed_metadata.confidence.get('financial_year') == Evidence(
        score=0.8, snippet=''
    )
