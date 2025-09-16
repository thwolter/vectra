from __future__ import annotations

import pytest

from app.repositories import JobRepository
from app.schemas.upload import JobStatus


@pytest.mark.needs_postgres
async def test_get_job_returns_correct_status(session, job_created, auth_client):
    r = auth_client.get(f'/api/v1/jobs/{job_created.id}')

    assert r.status_code == 200, r.text
    payload = r.json()
    assert payload['job_id'] == str(job_created.id)
    assert payload['status'] == job_created.status


@pytest.mark.needs_postgres
async def test_cannot_confirm_processing_job(session, job_created, auth_client):
    assert job_created.status == JobStatus.PROCESSING.value
    r = auth_client.patch(
        f'/api/v1/jobs/{job_created.id}/review',
        json={
            'confirm': True,
            'corrections': None,
        },
    )
    assert r.status_code == 409


@pytest.mark.needs_postgres
async def test_can_confirm_job(session, auth_client, ingestion_created_with_review):
    job = ingestion_created_with_review.job
    r = auth_client.patch(
        f'/api/v1/jobs/{job.id}/review',
        json={
            'confirm': True,
            'corrections': None,
        },
    )

    assert r.status_code == 200, r.text
    resp = r.json()
    assert resp['job_id'] == str(job.id)
    assert resp['status'] == JobStatus.COMPLETED.value

    # check the database
    job = await JobRepository.get(session, job_id=job.id, refresh=True)
    assert job is not None
    assert job.status == JobStatus.COMPLETED.value

    pm = job.proposed_metadata
    assert pm is not None
    assert pm['metadata'] == job.proposed_metadata['metadata']


@pytest.mark.needs_postgres
async def test_can_change_metadata_and_confirm_job(session, ingestion_created_with_review, auth_client):
    job = ingestion_created_with_review.job
    r = auth_client.patch(
        f'/api/v1/jobs/{job.id}/review',
        json={
            'confirm': True,
            'corrections': {
                'company': 'Gamma Holdings PLC',
                'financial_year': 2021,
            },
        },
    )

    assert r.status_code == 200, r.text
    resp = r.json()
    assert resp['job_id'] == str(job.id)
    assert resp['status'] == JobStatus.COMPLETED.value

    # check the database
    job = await JobRepository.get(session, job_id=job.id, refresh=True)
    assert job is not None

    pm = job.proposed_metadata
    assert pm is not None
    meta = pm['metadata']
    assert meta.get('company') == 'Gamma Holdings PLC'
    assert meta.get('financial_year') == 2021

    # Unchanged keys should remain from original proposal
    assert meta.get('document_type') == job.proposed_metadata['metadata']['document_type']
