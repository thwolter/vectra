import datetime as dt
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import UploadFile

from app.api.file import TemporaryUploadFile
from app.schemas.enums import CollectionEnum
from app.store.s3_store import S3Store


def get_store(client: MagicMock):
    _client = MagicMock()
    _client.__aenter__ = AsyncMock(return_value=client)
    _client.__aexit__ = AsyncMock(return_value=None)
    store = S3Store(collection=CollectionEnum.DEFAULT)
    # Override client factory to return our async context manager
    store.client_factory = lambda: _client  # type: ignore[assignment]
    return store


@pytest.mark.asyncio
async def test_save_original_calls_upload_fileobj(tiny_pdf_upload: UploadFile):
    client = MagicMock()
    client.upload_fileobj = AsyncMock(return_value=None)

    store = get_store(client)
    file = TemporaryUploadFile.from_upload(tiny_pdf_upload)

    await store.save_original(file, document_id=uuid.uuid4())
    assert client.upload_fileobj.call_count == 1


@pytest.mark.asyncio
async def test_save_markdown_calls_upload_fileobj():
    client = MagicMock()
    client.upload_fileobj = AsyncMock(return_value=None)

    store = get_store(client)

    await store.save_markdown('# Title\nBody', document_id=uuid.uuid4())
    assert client.upload_fileobj.call_count == 1


@pytest.mark.asyncio
async def test_delete_calls_list_and_delete_objects():
    client = MagicMock()
    client.list_objects_v2 = AsyncMock(
        return_value={
            'Contents': [
                {'Key': 'pfx/original.pdf'},
                {'Key': 'pfx/document.md'},
            ]
        }
    )
    client.delete_objects = AsyncMock(return_value=None)

    store = get_store(client)
    # Ensure predictable prefix matching inside delete
    store._prefix = lambda document_id: 'pfx/'  # type: ignore[attr-defined]

    ok = await store.delete(uuid.uuid4())

    assert ok is True
    assert client.list_objects_v2.call_count == 1
    assert client.delete_objects.call_count == 1


@pytest.mark.asyncio
async def test_delete_returns_true_when_nothing_to_delete():
    client = MagicMock()
    client.list_objects_v2 = AsyncMock(return_value={'Contents': []})
    client.delete_objects = AsyncMock(return_value=None)

    store = get_store(client)

    ok = await store.delete(uuid.uuid4())

    assert ok is True
    assert client.list_objects_v2.call_count == 1
    # Should not attempt deletion when there are no matching keys
    assert client.delete_objects.call_count == 0


@pytest.mark.asyncio
async def test_load_calls_get_object_and_reads_body():
    body = MagicMock()
    body.read = AsyncMock(return_value=b'data')

    client = MagicMock()
    client.get_object = AsyncMock(return_value={'Body': body})

    store = get_store(client)

    data = await store.load('some/key')

    assert data == b'data'
    assert client.get_object.call_count == 1
    assert body.read.call_count == 1


@pytest.mark.asyncio
async def test_info_calls_list_and_head_object():
    # Prepare a fake LastModified datetime-like object with isoformat
    last_modified = dt.datetime(2024, 1, 1, 12, 0, 0)

    client = MagicMock()
    client.list_objects_v2 = AsyncMock(
        return_value={'Contents': [{'Key': 'any/key', 'Size': 123, 'LastModified': last_modified}]}
    )
    client.head_object = AsyncMock(
        return_value={
            'ContentType': 'text/markdown; charset=utf-8',
            'ContentEncoding': None,
            'Metadata': {'a': 'b'},
        }
    )

    store = get_store(client)

    document_id = uuid.uuid4()
    info = await store.info(document_id)

    assert client.list_objects_v2.call_count == 1
    assert client.head_object.call_count == 1
    assert info.document_id == document_id
    assert isinstance(info.files, list) and len(info.files) == 1
