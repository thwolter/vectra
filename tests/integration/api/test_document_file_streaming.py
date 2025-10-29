import uuid

import pytest
from fastapi.testclient import TestClient

from api.file import TemporaryUploadFile
from core.db import scoped_session
from main import app
from repositories.exceptions import RecordNotFoundError
from schemas.enums import CollectionEnum
from services.factory import get_document_service
from services.factory import get_document_service as _get_document_service_dep
from store.local_store import LocalFileStore


@pytest.fixture
async def streaming_env(apple_report_first_page_upload):
    """Module-scoped setup for document file streaming tests.

    Prepares a LocalFileStore + DocumentService wired via FastAPI dependency override,
    uploads an original file and a markdown copy for a single document_id, and yields
    a tuple of (client, store, document_id).
    """
    document_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    store = LocalFileStore(CollectionEnum.DEFAULT.value)
    service = get_document_service()
    upload = TemporaryUploadFile.from_upload(apple_report_first_page_upload)
    digest = await upload.sha256_b64()

    class _Record:
        def __init__(self) -> None:
            self.id = document_id
            self.collection = CollectionEnum.DEFAULT.value
            self.tenant_id = tenant_id
            self.digest = digest

    record = _Record()

    class _Repo:
        async def get(self, _session, *, document_id: uuid.UUID):
            if document_id != record.id:
                raise RecordNotFoundError('not found')
            return record

    service.repo = _Repo()  # type: ignore[assignment]
    service._get_store = lambda _collection: store  # type: ignore[assignment]

    def _override_service():
        return service

    async def _session_override():  # pragma: no cover - simple stub for tests
        class _Session:
            pass

        return _Session()

    app.dependency_overrides[_get_document_service_dep] = _override_service  # type: ignore[attr-defined]
    app.dependency_overrides[scoped_session] = _session_override
    client = TestClient(app)

    await store.save_original(
        upload,
        document_id=document_id,
        digest=digest,
        tenant_id=tenant_id,
    )
    await store.save_markdown(
        '# Title\nHello',
        document_id=document_id,
        digest=digest,
        tenant_id=tenant_id,
    )

    try:
        yield client, store, document_id, tenant_id, digest
    finally:
        # Cleanup override after all tests in this module finish
        app.dependency_overrides.pop(_get_document_service_dep, None)  # type: ignore[attr-defined]
        app.dependency_overrides.pop(scoped_session, None)  # type: ignore[attr-defined]


@pytest.mark.integration
async def test_stream_markdown_success(streaming_env):
    client, store, document_id, tenant_id, digest = streaming_env

    r = client.get(f'/api/v1/documents/{document_id}/file/markdown')
    assert r.status_code == 200
    assert r.headers['content-type'].startswith('text/markdown')
    md_bytes = r.content

    info = await store.info(document_id=document_id, digest=digest, tenant_id=tenant_id)
    info_dict = info.model_dump()  # pydantic BaseModel -> dict
    md_key = next(f['key'] for f in info_dict['files'] if f['key'].endswith('document.md'))
    expected_md = await store.load(md_key)
    assert expected_md == md_bytes


@pytest.mark.integration
async def test_stream_original_success(streaming_env):
    client, store, document_id, tenant_id, digest = streaming_env

    r = client.get(f'/api/v1/documents/{document_id}/file/original')
    assert r.status_code == 200

    assert r.headers['content-type'].startswith('application/pdf')
    orig_bytes = r.content

    info = await store.info(document_id=document_id, digest=digest, tenant_id=tenant_id)
    info_dict = info.model_dump()
    orig_key = next(f['key'] for f in info_dict['files'] if f['key'].split('/')[-1].startswith('original'))
    expected_orig = await store.load(orig_key)
    assert expected_orig == orig_bytes


@pytest.mark.integration
async def test_stream_missing_file_returns_404(streaming_env):
    client, *_ = streaming_env

    missing_id = uuid.uuid4()
    r = client.get(f'/api/v1/documents/{missing_id}/file/original')
    assert r.status_code == 404
