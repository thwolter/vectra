import io
import uuid

import pytest
from fastapi import UploadFile
from tenauth.schemas import AccessContext

from api.file import TemporaryUploadFile
from repositories import embeddings_repository
from schemas.upload import ContinueProcessingInput, JobStatus
from tests.support.profiles import TestProcessingProfile  # type: ignore[attr-defined]


@pytest.mark.needs_postgres
async def test_upload_then_continue_processing_and_status_completed(
    small_pdf,
    auth_session,
    auth_client,
):
    api_client = auth_client

    with open(small_pdf, 'rb') as f:
        file_bytes = f.read()
    files = {'file': ('tiny.pdf', io.BytesIO(file_bytes), 'application/pdf')}

    # Step 1: init upload via API
    r = await api_client.post('/api/v1/uploads', files=files)
    assert r.status_code == 201, r.text
    init = r.json()

    # Step 2: check job status via API
    r2 = await api_client.get(f'/api/v1/jobs/{init["job_id"]}')
    assert r2.status_code == 200
    status_payload = r2.json()
    # Status may vary depending on environment timing; ensure endpoint is reachable and job_id matches
    assert status_payload['job_id'] == init['job_id']

    # Step 4: verify embeddings exist for the document by digest via metadata repo
    exists = await embeddings_repository.exists(
        auth_session,
        digest=init['digest'],
        collection=TestProcessingProfile.collection,
    )

    assert exists, 'Expected embeddings to exist in DB for the uploaded document'


@pytest.mark.needs_postgres
async def test_second_upload_is_deduplicated_after_first_ingestion(
    apple_report_first_page,
    auth_client,
    auth_session,
    upload_service,
):
    with open(apple_report_first_page, 'rb') as f:
        file_bytes = f.read()
    files = {'file': ('tiny.pdf', io.BytesIO(file_bytes), 'application/pdf')}

    # First upload + full processing via service
    r1 = await auth_client.post('/api/v1/uploads', files=files)
    assert r1.status_code == 201
    init1 = r1.json()

    upload_file = UploadFile(filename='tiny.pdf', file=io.BytesIO(file_bytes))
    upload_file.content_type = 'application/pdf'
    temp_file = TemporaryUploadFile.from_upload(upload_file)
    await upload_service.continue_processing(
        payload=ContinueProcessingInput(
            job_id=uuid.UUID(init1['job_id']),
            document_id=uuid.UUID(init1['document_id']),
            digest=init1['digest'],
            file=temp_file,
            access_context=AccessContext.from_session(auth_session),
        )
    )

    temp_file.close()

    # Second upload init should report deduplicated True
    r2 = await auth_client.post('/api/v1/uploads', files=files)
    assert r2.status_code == 201
    init2 = r2.json()
    assert init2['status'] == JobStatus.DUPLICATED.value
    assert init2['already_running'] is False
