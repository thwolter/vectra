import uuid
from typing import cast

import pytest
from fastapi.testclient import TestClient

from app.api.file import TemporaryUploadFile
from app.main import app
from app.schemas.enums import CollectionEnum
from app.services.document_service import DocumentService
from app.services.dependencies import get_document_service as _get_document_service_dep
from app.store.local_store import LocalFileStore
from app.store.protocols import StoreProtocol


@pytest.mark.integration
@pytest.mark.asyncio
async def test_stream_markdown_and_original_success(
    apple_report_first_page_upload, tmp_path
):
    # Use a dedicated DocumentService wired to the same LocalFileStore
    document_id = uuid.uuid4()
    store = LocalFileStore(CollectionEnum.DEFAULT, base_path=tmp_path)
    service = DocumentService(collection=CollectionEnum.DEFAULT)
    service.store = cast(StoreProtocol, store)

    def _override_service():
        return service

    app.dependency_overrides[_get_document_service_dep] = _override_service  # type: ignore[attr-defined]
    client = TestClient(app)

    # Save original and markdown
    upload = TemporaryUploadFile.from_upload(apple_report_first_page_upload)
    await store.save_original(upload, document_id=document_id)
    await store.save_markdown('# Title\nHello', document_id=document_id)

    # Stream markdown
    r = client.get(f'/api/v1/documents/{document_id}/file/markdown')
    assert r.status_code == 200
    assert r.headers['content-type'].startswith('text/markdown')
    md_bytes = r.content

    info = await store.info(document_id)
    info_dict = info.model_dump()  # pydantic BaseModel -> dict
    md_key = next(
        f['key'] for f in info_dict['files'] if f['key'].endswith('document.md')
    )
    expected_md = await store.load(md_key)
    assert expected_md == md_bytes

    # Stream original
    r2 = client.get(f'/api/v1/documents/{document_id}/file/original')
    assert r2.status_code == 200
    # content-type is application/pdf
    assert r2.headers['content-type'].startswith('application/pdf')
    orig_bytes = r2.content

    orig_key = next(
        f['key']
        for f in info_dict['files']
        if f['key'].split('/')[-1].startswith('original')
    )
    expected_orig = await store.load(orig_key)
    assert expected_orig == orig_bytes

    # Cleanup overrides
    app.dependency_overrides.pop(_get_document_service_dep, None)  # type: ignore[attr-defined]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_stream_missing_file_returns_404(tmp_path):
    service = DocumentService(collection=CollectionEnum.DEFAULT)
    store = LocalFileStore(CollectionEnum.DEFAULT, base_path=tmp_path)
    service.store = cast(StoreProtocol, store)

    def _override_service():
        return service

    app.dependency_overrides[_get_document_service_dep] = _override_service  # type: ignore[attr-defined]
    client = TestClient(app)

    missing_id = uuid.uuid4()
    r = client.get(f'/api/v1/documents/{missing_id}/file/original')
    assert r.status_code == 404

    # Cleanup overrides
    app.dependency_overrides.pop(_get_document_service_dep, None)  # type: ignore[attr-defined]
