from __future__ import annotations

import pytest


@pytest.mark.needs_postgres
async def test_get_job_returns_correct_status(session, job_created, auth_client):
    r = auth_client.get(f'/api/v1/jobs/{job_created.id}')

    assert r.status_code == 200, r.text
    payload = r.json()
    assert payload['job_id'] == str(job_created.id)
    assert payload['status'] == job_created.status
