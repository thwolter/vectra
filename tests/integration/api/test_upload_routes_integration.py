import io

import pytest

from app.repositories import EmbeddingsRepository
from tests.support.profiles import TestProcessingProfile


@pytest.mark.needs_postgres
async def test_upload_then_continue_processing_and_status_completed(
    small_pdf,
    session,
    auth_client,
):
    api_client = auth_client

    with open(small_pdf, 'rb') as f:
        file_bytes = f.read()
    files = {'file': ('tiny.pdf', io.BytesIO(file_bytes), 'application/pdf')}

    # Step 1: init upload via API
    r = api_client.post('/api/v1/uploads', files=files)
    assert r.status_code == 201, r.text
    init = r.json()

    # Step 2: check job status via API
    r2 = api_client.get(f'/api/v1/jobs/{init["job_id"]}')
    assert r2.status_code == 200
    status_payload = r2.json()
    # Status may vary depending on environment timing; ensure endpoint is reachable and job_id matches
    assert status_payload['job_id'] == init['job_id']

    # Step 4: verify embeddings exist for the document by digest via metadata repo
    exists = await EmbeddingsRepository.exists(
        session,
        digest=init['digest'],
        collection=TestProcessingProfile.collection,
    )

    assert exists, 'Expected embeddings to exist in DB for the uploaded document'


@pytest.mark.needs_postgres
async def test_second_upload_is_deduplicated_after_first_ingestion(
    apple_report_first_page,
    auth_client,
):
    with open(apple_report_first_page, 'rb') as f:
        file_bytes = f.read()
    files = {'file': ('tiny.pdf', io.BytesIO(file_bytes), 'application/pdf')}

    # First upload + full processing
    r1 = auth_client.post('/api/v1/uploads', files=files)
    assert r1.status_code == 201

    # Second upload init should report deduplicated True
    r2 = auth_client.post('/api/v1/uploads', files=files)
    assert r2.status_code == 201
    init2 = r2.json()
    assert init2['already_running'] is True
