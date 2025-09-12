from __future__ import annotations

import pytest

from app.repositories.job_repository import Job
from tests.helper import make_api_client
from app.schemas.upload import JobStatus


@pytest.mark.integration
@pytest.mark.needs_postgres
@pytest.mark.asyncio
async def test_get_job_returns_status(session, created_job_id):
    api_client = make_api_client()

    r = api_client.get(f'/api/v1/jobs/{created_job_id}')

    assert r.status_code == 200, r.text
    payload = r.json()
    assert payload['job_id'] == str(created_job_id)
    assert payload['status'] in {
        JobStatus.PROCESSING.value,
        JobStatus.NEEDS_REVIEW.value,
        JobStatus.COMPLETED.value,
    }


@pytest.mark.integration
@pytest.mark.needs_postgres
@pytest.mark.asyncio
async def test_review_job_confirm_only(session, created_job_id):
    api_client = make_api_client()
    body = {
        'confirm': True,
        'corrections': None,
    }
    r = api_client.patch(f'/api/v1/jobs/{created_job_id}/review', json=body)

    # Assert: response and DB should reflect COMPLETED and preserved metadata
    assert r.status_code == 200, r.text
    resp = r.json()
    assert resp['job_id'] == str(created_job_id)
    assert resp['status'] == JobStatus.COMPLETED.value

    # Verify DB entry updated
    status = await Job.get_status(session, job_id=created_job_id)
    assert status is not None
    assert status.status == JobStatus.COMPLETED

    pm = status.proposed_metadata
    assert pm is not None
    meta = pm.metadata
    assert meta.get('company') == 'ACME Inc.'
    assert meta.get('financial_year') == 2024
    assert meta.get('document_type') == '10-Q'


@pytest.mark.integration
@pytest.mark.needs_postgres
@pytest.mark.asyncio
async def test_review_job_with_corrections(session, created_job_id):
    api_client = make_api_client()
    body = {
        'confirm': True,
        'corrections': {
            'company': 'Gamma Holdings PLC',
            'financial_year': 2021,
        },
    }
    r = api_client.patch(f'/api/v1/jobs/{created_job_id}/review', json=body)

    # Assert response
    assert r.status_code == 200, r.text
    resp = r.json()
    assert resp['job_id'] == str(created_job_id)
    assert resp['status'] == JobStatus.COMPLETED.value

    # Verify DB reflects corrected metadata
    status = await Job.get_status(session, job_id=created_job_id)
    assert status is not None
    assert status.status == JobStatus.COMPLETED

    pm = status.proposed_metadata
    assert pm is not None
    meta = pm.metadata
    assert meta.get('company') == 'Gamma Holdings PLC'
    assert meta.get('financial_year') == 2021

    # Unchanged keys should remain from original proposal
    assert meta.get('document_type') == '10-Q'
