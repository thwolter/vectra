from __future__ import annotations


async def test_get_job_returns_correct_status(job_created, auth_client):
    r = await auth_client.get(f'/api/v1/jobs/{job_created.id}')

    assert r.status_code == 200, r.text
    payload = r.json()
    assert payload['job_id'] == str(job_created.id)
    assert payload['status'] == job_created.status
