import time
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.metadata.schemas import FinanceReportHints
from app.repositories import EmbeddingsRepository
from app.schemas.enums import CollectionEnum
from app.store.local_store import LocalFileStore
from tests.helper import make_client_financial, make_files_param


def _poll_job(client: TestClient, job_id: str, *, timeout: float = 90.0, interval: float = 0.5) -> str:
    deadline = time.time() + timeout
    while time.time() < deadline:
        rs = client.get(f'/api/v1/jobs/{job_id}')
        rs.raise_for_status()
        status = rs.json()['status']
        if status in {'needs_review', 'completed'}:
            return status
        time.sleep(interval)
    return status  # last seen


def _store_keys_for_digest(document_id: UUID, tmp_path) -> list[str]:
    import anyio

    store = LocalFileStore(collection=CollectionEnum.FINANCIAL, base_path=tmp_path)

    async def _info(*args, **kwargs):
        return await store.info(document_id=document_id)

    info = anyio.run(_info, None)
    return [f.key for f in info.files]


@pytest.mark.e2e
@pytest.mark.needs_postgres
def test_financial_upload_review_then_patch(apple_report_first_page, tmp_path, session):
    client = make_client_financial(tmp_path)
    files = make_files_param(apple_report_first_page)

    # Provide incomplete hints to force needs_review (missing doc_type/reporting_year)
    hints_json = FinanceReportHints(company='Acme Corp', document_type=None, financial_year=None).model_dump_json(
        exclude_none=True
    )

    data = {'hints': hints_json}

    r = client.post('/api/v1/uploads', files=files, data=data)
    assert r.status_code == 200, r.text
    body = r.json()
    job_id = body['job_id']
    document_id = body['document_id']
    digest = body['digest']

    # Poll for needs_review
    status = _poll_job(client, job_id)
    assert status in {'needs_review'}

    if status == 'needs_review':
        payload = {
            'confirm': True,
            'corrections': {
                'company_legal_name': 'Contoso GmbH',
                'doc_type': 'annual_report',
                'reporting_year': 2022,
            },
        }
        pr = client.patch(f'/api/v1/jobs/{job_id}/review', json=payload)
        assert pr.status_code == 200, pr.text
        assert pr.json()['status'] in {
            'completed',
            'needs_review',
        }  # should be completed

        # Poll until completed
        deadline2 = time.time() + 60
        while time.time() < deadline2:
            rs = client.get(f'/api/v1/jobs/{job_id}')
            assert rs.status_code == 200
            js = rs.json()
            if js['status'] == 'completed':
                break
            time.sleep(0.5)
        assert client.get(f'/api/v1/jobs/{job_id}').json()['status'] == 'completed'

    # Verify store artifacts in FINANCIAL collection
    keys = _store_keys_for_digest(document_id=document_id, tmp_path=tmp_path)
    assert any(k.endswith('original.pdf') or k.endswith('original.pdf.gz') for k in keys), keys
    assert any(k.endswith('document.md') for k in keys), keys

    async def _get_all_md(*args, **kwargs):
        return await EmbeddingsRepository.get_metadata(
            session, digest=digest, collection=CollectionEnum.FINANCIAL.value
        )

    import anyio

    all_md = anyio.run(_get_all_md, None)
    assert all_md, 'No embeddings metadata found'
    for md in all_md:
        assert md.get('digest') == digest
        assert md.get('company_legal_name') == 'Contoso GmbH'
        assert md.get('doc_type') == 'annual_report'
        assert md.get('reporting_year') == 2022
