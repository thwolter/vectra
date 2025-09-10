from __future__ import annotations

import pytest

from tests.helper import arrange_job_with_metadata, make_api_client
from app.schemas.upload import JobStatus


@pytest.mark.integration
@pytest.mark.needs_postgres
@pytest.mark.asyncio
async def test_get_job_returns_status():
    # Arrange
    job_id, _ = await arrange_job_with_metadata(
        company='Acme Inc',
        financial_year=2024,
        document_type='10-K',
        digest='47DEQpj8HBSa+/TImW+5JCeuQeRkm5NMpJWZG3hSuFU=',
        original_filename='sample.pdf',
        size_bytes=1234,
    )

    # Act
    api_client = make_api_client()
    r = api_client.get(f'/api/v1/jobs/{job_id}')

    # Assert
    assert r.status_code == 200, r.text
    payload = r.json()
    assert payload['job_id'] == str(job_id)
    assert payload['status'] in {
        JobStatus.PROCESSING.value,
        JobStatus.NEEDS_REVIEW.value,
        JobStatus.COMPLETED.value,
    }


@pytest.mark.integration
@pytest.mark.needs_postgres
@pytest.mark.asyncio
async def test_review_job_confirm_only():
    # Arrange
    job_id, job_repo = await arrange_job_with_metadata(
        company='Beta Corp',
        financial_year=2023,
        document_type='Annual Report',
        digest='50DEQpj8HBSa+/TImW+5JCeuQeRkm5NMpJWZG3hSuFU=',
        original_filename='beta.pdf',
        size_bytes=999,
    )

    # Act
    api_client = make_api_client()
    body = {
        'confirm': True,
        'corrections': None,
    }
    r = api_client.patch(f'/api/v1/jobs/{job_id}/review', json=body)

    # Assert: response and DB should reflect COMPLETED and preserved metadata
    assert r.status_code == 200, r.text
    resp = r.json()
    assert resp['job_id'] == str(job_id)
    assert resp['status'] == JobStatus.COMPLETED.value

    # Verify DB entry updated
    status = await job_repo.get_status(job_id=job_id)
    assert status is not None
    assert status.status == JobStatus.COMPLETED
    pm = status.proposed_metadata
    meta = pm.metadata
    assert meta.get('company') == 'Beta Corp'
    assert meta.get('financial_year') == 2023
    assert meta.get('document_type') == 'Annual Report'


@pytest.mark.integration
@pytest.mark.needs_postgres
@pytest.mark.asyncio
async def test_review_job_with_corrections():
    # Arrange
    job_id, job_repo = await arrange_job_with_metadata(
        company='Gamma LLC',
        financial_year=2022,
        document_type='10-Q',
        digest='60DEQpj8HBSa+/TImW+5JCeuQeRkm5NMpJWZG3hSuFU=',
        original_filename='gamma.pdf',
        size_bytes=2048,
    )

    # Act: send corrections and confirm
    api_client = make_api_client()
    body = {
        'confirm': True,
        'corrections': {
            'company': 'Gamma Holdings PLC',
            'financial_year': 2021,
        },
    }
    r = api_client.patch(f'/api/v1/jobs/{job_id}/review', json=body)

    # Assert response
    assert r.status_code == 200, r.text
    resp = r.json()
    assert resp['job_id'] == str(job_id)
    assert resp['status'] == JobStatus.COMPLETED.value

    # Verify DB reflects corrected metadata
    status = await job_repo.get_status(job_id=job_id)
    assert status is not None
    assert status.status == JobStatus.COMPLETED
    pm = status.proposed_metadata
    meta = pm.metadata
    assert meta.get('company') == 'Gamma Holdings PLC'
    assert meta.get('financial_year') == 2021

    # Unchanged keys should remain from original proposal
    assert meta.get('document_type') == '10-Q'
