import io
import uuid
from unittest.mock import create_autospec, AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.protocols.services import UploadServiceProtocol, JobServiceProtocol
from app.schemas.upload import (
    UploadInitResponse,
    JobStatusResponse,
    JobReviewResponse,
    JobStatus,
    JobProgress,
    JobReviewPayload,
)
from app.metadata.schemas import NoopHints, FinanceReportHints
from app.services.factory import get_upload_service, get_job_service

JOB_ID = uuid.uuid4()
DOCUMENT_ID = uuid.uuid4()


@pytest.fixture()
def api_client(monkeypatch, digest_str, fake_auth_client) -> TestClient:
    client = fake_auth_client
    app = client.app

    upload_mock: UploadServiceProtocol = create_autospec(
        UploadServiceProtocol, instance=True, spec_set=True
    )
    job_mock: JobServiceProtocol = create_autospec(
        JobServiceProtocol, instance=True, spec_set=True
    )

    upload_mock.start_document_upload = AsyncMock(
        return_value=UploadInitResponse(
            job_id=JOB_ID,
            document_id=DOCUMENT_ID,
            status=JobStatus.PROCESSING,
            deduplicated=False,
            digest=digest_str,
            original_filename='tiny.pdf',
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
            proposed_metadata=None,
        )
    )
    job_mock.review_job = AsyncMock(
        return_value=JobReviewResponse(
            job_id=JOB_ID,
            status=JobStatus.COMPLETED,
        )
    )

    app.dependency_overrides[get_upload_service] = lambda: upload_mock
    app.dependency_overrides[get_job_service] = lambda: job_mock

    client.upload_mock = upload_mock
    client.job_mock = job_mock
    return client


def test_upload_document_with_finance_hints_is_parsed(api_client):
    # Prepare a small file
    file_bytes = b'%PDF-1.4\n%\xe2\xe3\xcf\xd3'  # trivial PDF header bytes
    hints_json = FinanceReportHints(
        company='Acme Corp',
        document_type='10-K',
        financial_year=2024,
    ).model_dump_json()

    files = {'file': ('tiny.pdf', io.BytesIO(file_bytes), 'application/pdf')}
    data = {'hints': hints_json}

    r = api_client.post('/api/v1/uploads', files=files, data=data)
    assert r.status_code == 201, r.text

    data = r.json()
    assert data['job_id'] == str(JOB_ID)
    assert data['document_id'] == str(DOCUMENT_ID)

    mock_service = api_client.upload_mock  # type: ignore[attr-defined]
    assert mock_service.start_document_upload.await_count == 1
    assert mock_service.continue_processing.await_count == 1

    _, kwargs = mock_service.start_document_upload.await_args
    passed_hints = kwargs['payload'].hints
    assert isinstance(passed_hints, FinanceReportHints)


def test_upload_document_allows_missing_hints(api_client: TestClient):
    files = {'file': ('tiny.txt', io.BytesIO(b'hello world'), 'text/plain')}

    r = api_client.post('/api/v1/uploads', files=files, data=None)
    assert r.status_code == 201, r.text

    data = r.json()
    assert data['job_id'] == str(JOB_ID)
    assert data['document_id'] == str(DOCUMENT_ID)

    mock_service = api_client.upload_mock  # type: ignore[attr-defined]
    assert mock_service.start_document_upload.await_count == 1
    assert mock_service.continue_processing.await_count == 1

    _, kwargs = mock_service.start_document_upload.await_args
    passed_hints = kwargs['payload'].hints
    assert isinstance(passed_hints, NoopHints)


def test_upload_document_invalid_hints_json_returns_422(api_client: TestClient):
    # Malformed JSON
    files = {'file': ('tiny.pdf', io.BytesIO(b'123'), 'application/pdf')}
    # Malformed JSON as plain form field to trigger validation error
    r = api_client.post('/api/v1/uploads', files=files, data={'hints': '{bad json]}'})
    assert r.status_code == 422
    detail = r.json().get('detail', '')
    assert detail


def test_get_job_status_returns_payload(api_client: TestClient):
    r = api_client.get(f'/api/v1/jobs/{JOB_ID}')
    assert r.status_code == 200
    body = r.json()
    assert body['job_id'] == str(JOB_ID)
    assert body['status'] == 'completed'
    assert body['progress']['percent'] == 100
    assert body['progress']['step'] == 'finalize'


def test_review_job_happy_path(api_client: TestClient):
    payload = JobReviewPayload(
        confirm=True,
        corrections={
            'company_legal_name': 'ACME, Inc.',
            'doc_type': '10-K',
            'financial_year': 2024,
        },
    ).model_dump()
    r = api_client.patch(f'/api/v1/jobs/{JOB_ID}/review', json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body['job_id'] == str(JOB_ID)
    assert body['status'] == 'completed'
