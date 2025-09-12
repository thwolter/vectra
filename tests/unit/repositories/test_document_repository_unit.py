import uuid

import pytest

from app.repositories.documents import Document
from app.repositories.schemas import DocumentCreate


@pytest.mark.asyncio
async def test_create_inserts_then_selects_and_returns_id(
    monkeypatch, fake_session_class, digest_str
):
    # Prepare session that will return a row with (id,) for fetchone
    new_id = uuid.uuid4()
    unit_session = fake_session_class(rows=[(new_id,)], scalar=str(uuid.uuid4()))

    # Stable store name for assertions in later tests (not strictly needed here)
    import app.repositories.documents as docDocument_module

    monkeypatch.setattr(
        docDocument_module.settings, 'document_store', 'test-store', raising=True
    )

    data = DocumentCreate(
        collection='default',
        digest=digest_str,
        original_filename='file.pdf',
        content_type='application/pdf',
        size_bytes=123,
        meta={'k': 'v'},
    )

    got_id = await Document.create(unit_session, data=data)

    # Assertions: a single INSERT ... RETURNING was executed, commit called once
    assert len(unit_session.executed) >= 1
    insert_sqls = [
        sql for sql, _ in unit_session.executed if 'INSERT INTO documents' in sql
    ]
    assert insert_sqls, 'No INSERT executed'
    assert 'RETURNING id' in insert_sqls[0]
    assert unit_session.commits == 1
    assert got_id == new_id


@pytest.mark.asyncio
async def test_get_returns_document_model(fake_session_class):
    # Prepare row matching SELECT order in Documentsitory
    doc_id = uuid.uuid4()
    from datetime import datetime

    created_at = datetime.now()
    row = {
        'id': doc_id,
        'tenant_id': None,
        'collection': 'default',
        'digest': 'b' * 64,
        'original_filename': 'x.pdf',
        'content_type': 'application/pdf',
        'size_bytes': 456,
        'original_uri': 's3://bucket/original',
        'markdown_uri': 's3://bucket/markdown',
        'store': None,
        'meta': {'m': 1},
        'created_at': created_at,
        'updated_at': created_at,
        'created_by': None,
    }

    unit_session = fake_session_class(rows=[row])

    doc = await Document.get(unit_session, id=doc_id)

    # Build expected dict and compare with the dumped model
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
    monkeypatch,
    fake_session_class,
):
    unit_session = fake_session_class()

    import app.repositories.documents as docDocument_module

    monkeypatch.setattr(
        docDocument_module.settings, 'document_store', 'test-store', raising=True
    )

    did = uuid.uuid4()
    await Document.update_uris(
        unit_session,
        id=did,
        original_uri='s3://b/o',
        markdown_uri='s3://b/m',
    )

    # Ensure execute was called with params containing our id, store, and URIs
    assert len(unit_session.executed) == 1
    sql, params = unit_session.executed[0]
    assert 'UPDATE documents SET' in sql
    assert params['id'] == did
    assert params['store'] == 'test-store'
    assert params['original_uri'] == 's3://b/o'
    assert params['markdown_uri'] == 's3://b/m'
    assert unit_session.commits == 1


@pytest.mark.asyncio
async def test_update_meta_by_id_updates_meta(
    fake_session_class,
):
    unit_session = fake_session_class()

    did = uuid.uuid4()
    new_meta = {'company': 'ACME', 'year': 2024}
    await Document.update_metadata(unit_session, id=did, metadata=new_meta)

    assert len(unit_session.executed) == 1
    sql, params = unit_session.executed[0]
    assert 'UPDATE documents SET meta' in sql
    assert params['id'] == did
    assert params['meta'] == new_meta
    assert unit_session.commits == 1


@pytest.mark.asyncio
async def test_delete_by_id_executes_and_commits(
    fake_session_class,
):
    # Prepare session to simulate a successful DELETE ... RETURNING with one row
    did = uuid.uuid4()
    unit_session = fake_session_class(rows=[(did,)])

    deleted = await Document.delete(unit_session, id=did)

    # Assertions
    assert deleted is True
    assert len(unit_session.executed) == 1
    sql, params = unit_session.executed[0]
    assert 'DELETE FROM documents' in sql
    assert 'RETURNING id' in sql
    assert params['id'] == did
    assert unit_session.commits == 1
