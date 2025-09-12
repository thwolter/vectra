import uuid
from datetime import datetime, timezone

import pytest

from app.repositories import Document
from app.repositories.models import DocumentRecord


@pytest.mark.asyncio
async def test_get_returns_document_model(fake_session_class):
    # Arrange: a persisted record the ORM would return
    doc_id = uuid.uuid4()
    created_at = datetime.now(timezone.utc)
    rec = DocumentRecord(
        id=doc_id,
        tenant_id=None,
        collection='default',
        digest='b' * 64,
        original_filename='x.pdf',
        content_type='application/pdf',
        size_bytes=456,
        original_uri='s3://bucket/original',
        markdown_uri='s3://bucket/markdown',
        store=None,
        meta={'m': 1},
        created_at=created_at,
        created_by=None,
    )

    unit_session = fake_session_class()

    async def _get(model, key):
        assert model is DocumentRecord
        assert key == doc_id
        return rec

    unit_session.get = _get  # monkeypatch the async get used by SQLModel

    # Act
    doc = await Document.get(unit_session, id=doc_id)

    # Assert (behavioural, not SQL-based)
    expected = {
        'id': doc_id,
        'collection': 'default',
        'digest': 'b' * 64,
        'original_filename': 'x.pdf',
        'content_type': 'application/pdf',
        'size_bytes': 456,
        'original_uri': 's3://bucket/original',
        'markdown_uri': 's3://bucket/markdown',
        'meta': {'m': 1},
        'created_at': created_at,
    }
    dumped = doc.model_dump()
    assert {k: dumped[k] for k in expected.keys()} == expected


@pytest.mark.asyncio
async def test_update_uris_by_id_updates_store_and_uris(
    monkeypatch, fake_session_class
):
    unit_session = fake_session_class()

    import app.repositories.documents as documents_module

    # Ensure we write the configured store
    monkeypatch.setattr(
        documents_module.settings, 'document_store', 'test-store', raising=True
    )

    did = uuid.uuid4()
    rec = DocumentRecord(
        id=did,
        tenant_id=None,
        collection='default',
        digest='b' * 64,
        original_filename='x.pdf',
        content_type='application/pdf',
        size_bytes=1,
        meta=None,
        created_by=None,
        created_at=datetime.now(timezone.utc),
    )

    async def _get(model, key):
        assert model is DocumentRecord
        assert key == did
        return rec

    unit_session.get = _get  # SQLModel get()

    # Act
    await Document.update_uris(
        unit_session,
        id=did,
        original_uri='s3://b/o',
        markdown_uri='s3://b/m',
    )

    # Assert: record mutated + commit called
    assert rec.store == 'test-store'
    assert rec.original_uri == 's3://b/o'
    assert rec.markdown_uri == 's3://b/m'
    assert unit_session.commits == 1
