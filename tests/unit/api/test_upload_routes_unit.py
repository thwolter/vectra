import io
import uuid
from unittest.mock import AsyncMock, create_autospec

import pytest
from fastapi.testclient import TestClient

from app.protocols.services import JobServiceProtocol, UploadServiceProtocol
from app.schemas.upload import (
    JobProgress,
    JobStatus,
    JobStatusResponse,
    UploadInitResponse,
)
from app.services.factory import get_job_service, get_upload_service

JOB_ID = uuid.uuid4()
DOCUMENT_ID = uuid.uuid4()


@pytest.fixture()
def api_client(monkeypatch, digest_random, auth_client) -> TestClient:
    client = auth_client
    app = client.app

    upload_mock: UploadServiceProtocol = create_autospec(UploadServiceProtocol, instance=True, spec_set=True)
    job_mock: JobServiceProtocol = create_autospec(JobServiceProtocol, instance=True, spec_set=True)

    upload_mock.initiate_document_intake = AsyncMock(
        return_value=UploadInitResponse(
            job_id=JOB_ID,
            document_id=DOCUMENT_ID,
            status=JobStatus.PROCESSING,
            digest=digest_random,
            original_filename='tiny.pdf',
            already_running=False,
        )
    )
    upload_mock.continue_processing = AsyncMock(return_value=None)

    job_mock.get_status = AsyncMock(
        return_value=JobStatusResponse(
            job_id=JOB_ID,
            status=JobStatus.COMPLETED,
            progress=JobProgress(percent=100, step='finalize'),
            warnings=[],
            errors=[],
        )
    )

    app.dependency_overrides[get_upload_service] = lambda: upload_mock
    app.dependency_overrides[get_job_service] = lambda: job_mock

    enqueue_mock = AsyncMock()
    monkeypatch.setattr('app.api.v1.upload_routes.enqueue_upload_processing', enqueue_mock)

    client.upload_mock = upload_mock
    client.job_mock = job_mock
    client.enqueue_mock = enqueue_mock
    return client


def test_upload_document_triggers_pipeline(api_client: TestClient):
    file_bytes = b'%PDF-1.4\n%\xe2\xe3\xcf\xd3'
    files = {'file': ('tiny.pdf', io.BytesIO(file_bytes), 'application/pdf')}

    response = api_client.post('/api/v1/uploads', files=files)
    assert response.status_code == 201, response.text

    body = response.json()
    assert body['job_id'] == str(JOB_ID)
    assert body['document_id'] == str(DOCUMENT_ID)

    mock_service = api_client.upload_mock  # type: ignore[attr-defined]
    mock_service.initiate_document_intake.assert_awaited_once()
    api_client.enqueue_mock.assert_awaited_once()  # type: ignore[attr-defined]


def test_upload_document_duplicate_skips_pipeline(api_client: TestClient, digest_random):
    duplicate_response = UploadInitResponse(
        job_id=JOB_ID,
        document_id=DOCUMENT_ID,
        status=JobStatus.DUPLICATED,
        digest=digest_random,
        original_filename='tiny.pdf',
        already_running=False,
    )
    api_client.upload_mock.initiate_document_intake.return_value = duplicate_response  # type: ignore[attr-defined]

    file_bytes = b'%PDF-1.4\n%\xe2\xe3\xcf\xd3'
    files = {'file': ('tiny.pdf', io.BytesIO(file_bytes), 'application/pdf')}

    response = api_client.post('/api/v1/uploads', files=files)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body['status'] == JobStatus.DUPLICATED.value

    api_client.enqueue_mock.assert_not_awaited()  # type: ignore[attr-defined]


def test_get_job_status_returns_payload(api_client: TestClient):
    response = api_client.get(f'/api/v1/jobs/{JOB_ID}')
    assert response.status_code == 200
    body = response.json()
    assert body['job_id'] == str(JOB_ID)
    assert body['status'] == 'completed'
    assert body['progress']['percent'] == 100
    assert body['progress']['step'] == 'finalize'
