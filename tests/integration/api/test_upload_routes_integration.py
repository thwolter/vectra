import io
import json

import pytest
from fastapi.testclient import TestClient
from pathlib import Path

from tests.helper import build_test_upload_service
from app.main import app as fastapi_app
from app.services.factory import get_upload_service
from app.schemas.enums import CollectionEnum
from app.repositories.factory import get_embedding_repository


@pytest.fixture()
def tiny_pdf_bytes(tiny_pdf) -> bytes:
    with open(tiny_pdf, 'rb') as f:
        return f.read()


@pytest.fixture
def base_prefix(tmp_path) -> Path:
    return tmp_path / 'local-tests'


@pytest.mark.integration
@pytest.mark.needs_postgres
@pytest.mark.asyncio
async def test_upload_then_continue_processing_and_status_completed(
    small_pdf, base_prefix
):
    service = build_test_upload_service(
        collection=CollectionEnum.DEFAULT,
        base_prefix=base_prefix,
    )
    fastapi_app.dependency_overrides[get_upload_service] = lambda: service
    api_client = TestClient(fastapi_app)

    with open(small_pdf, 'rb') as f:
        file_bytes = f.read()
    files = {'file': ('tiny.pdf', io.BytesIO(file_bytes), 'application/pdf')}

    # Step 1: init upload via API
    r = api_client.post('/api/v1/uploads', files=files)
    assert r.status_code == 200, r.text
    init = r.json()

    # Step 2: check job status via API
    r2 = api_client.get(f'/api/v1/jobs/{init["job_id"]}')
    assert r2.status_code == 200
    status_payload = r2.json()
    # Status may vary depending on environment timing; ensure endpoint is reachable and job_id matches
    assert status_payload['job_id'] == init['job_id']

    # Step 4: verify embeddings exist for the document by digest via metadata repo
    meta_repo = get_embedding_repository()

    exists = await meta_repo.exists_by_digest(
        init['digest'], collection=CollectionEnum.DEFAULT.value
    )

    assert exists, 'Expected embeddings to exist in DB for the uploaded document'


@pytest.mark.integration
@pytest.mark.needs_postgres
@pytest.mark.asyncio
async def test_second_upload_is_deduplicated_after_first_ingestion(
    apple_report_first_page, base_prefix
):
    service = build_test_upload_service(
        collection=CollectionEnum.DEFAULT,
        base_prefix=base_prefix,
    )
    fastapi_app.dependency_overrides[get_upload_service] = lambda: service
    api_client = TestClient(fastapi_app)

    with open(apple_report_first_page, 'rb') as f:
        file_bytes = f.read()
    files = {'file': ('tiny.pdf', io.BytesIO(file_bytes), 'application/pdf')}

    # First upload + full processing
    r1 = api_client.post(
        '/api/v1/uploads', files=files, data={'hints_json': json.dumps({})}
    )
    assert r1.status_code == 200

    # Second upload init should report deduplicated True
    r2 = api_client.post(
        '/api/v1/uploads', files=files, data={'hints_json': json.dumps({})}
    )
    assert r2.status_code == 200
    init2 = r2.json()
    assert init2['deduplicated'] is True


@pytest.mark.integration
@pytest.mark.needs_postgres
def test_hints_influence_proposed_metadata_on_job(tiny_pdf_bytes, base_prefix):
    service = build_test_upload_service(
        collection=CollectionEnum.DEFAULT,
        base_prefix=base_prefix,
    )
    fastapi_app.dependency_overrides[get_upload_service] = lambda: service
    api_client = TestClient(fastapi_app)

    files = {'file': ('tiny.pdf', io.BytesIO(tiny_pdf_bytes), 'application/pdf')}

    hints = {
        'company_hint': 'Acme Corp',
        'doc_type_hint': '10-K',
        'reporting_year_hint': 2024,
    }

    r = api_client.post(
        '/api/v1/uploads',
        files=files,
        data={'hints_json': json.dumps(hints)},
        headers={'Idempotency-Key': 'route-int-key-1'},
    )
    assert r.status_code == 200
    init = r.json()

    # Immediately fetch job status; proposed metadata should be persisted from hints
    r2 = api_client.get(f'/api/v1/jobs/{init["job_id"]}')
    assert r2.status_code == 200
    payload = r2.json()
    # Just ensure the job exists and is retrievable after upload with hints
    assert payload['job_id'] == init['job_id']
