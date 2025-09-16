import uuid

import pytest
from fastapi.testclient import TestClient

from app.api.file import TemporaryUploadFile
from app.main import app
from app.schemas.enums import CollectionEnum
from app.services.dependencies import get_document_service as _get_document_service_dep
from app.services.document_service import DocumentService
from app.store.local_store import LocalFileStore


@pytest.fixture
async def streaming_env(apple_report_first_page_upload):
    """Module-scoped setup for document file streaming tests.

    Prepares a LocalFileStore + DocumentService wired via FastAPI dependency override,
    uploads an original file and a markdown copy for a single document_id, and yields
    a tuple of (client, store, document_id).
    """
    document_id = uuid.uuid4()
    store = LocalFileStore(CollectionEnum.DEFAULT)
    service = DocumentService(collection=CollectionEnum.DEFAULT)
    service.store = store

    def _override_service():
        return service

    app.dependency_overrides[_get_document_service_dep] = _override_service  # type: ignore[attr-defined]
    client = TestClient(app)

    upload = TemporaryUploadFile.from_upload(apple_report_first_page_upload)
    await store.save_original(upload, document_id=document_id)
    await store.save_markdown('# Title\nHello', document_id=document_id)

    try:
        yield client, store, document_id
    finally:
        # Cleanup override after all tests in this module finish
        app.dependency_overrides.pop(_get_document_service_dep, None)  # type: ignore[attr-defined]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_stream_markdown_success(streaming_env):
    client, store, document_id = streaming_env

    r = client.get(f'/api/v1/documents/{document_id}/file/markdown')
    assert r.status_code == 200
    assert r.headers['content-type'].startswith('text/markdown')
    md_bytes = r.content

    info = await store.info(document_id)
    info_dict = info.model_dump()  # pydantic BaseModel -> dict
    md_key = next(f['key'] for f in info_dict['files'] if f['key'].endswith('document.md'))
    expected_md = await store.load(md_key)
    assert expected_md == md_bytes


@pytest.mark.integration
@pytest.mark.asyncio
async def test_stream_original_success(streaming_env):
    client, store, document_id = streaming_env

    r = client.get(f'/api/v1/documents/{document_id}/file/original')
    assert r.status_code == 200

    assert r.headers['content-type'].startswith('application/pdf')
    orig_bytes = r.content

    info = await store.info(document_id)
    info_dict = info.model_dump()
    orig_key = next(f['key'] for f in info_dict['files'] if f['key'].split('/')[-1].startswith('original'))
    expected_orig = await store.load(orig_key)
    assert expected_orig == orig_bytes


@pytest.mark.integration
@pytest.mark.asyncio
async def test_stream_missing_file_returns_404(streaming_env):
    client, _store, _doc_id = streaming_env

    missing_id = uuid.uuid4()
    r = client.get(f'/api/v1/documents/{missing_id}/file/original')
    assert r.status_code == 404
