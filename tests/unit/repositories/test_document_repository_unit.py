import uuid

import pytest

from app.repositories.documents import DocumentRepository
from app.repositories.schemas import DocumentCreate


@pytest.mark.asyncio
async def test_create_inserts_then_selects_and_returns_id(
    monkeypatch, fake_session_class, fake_db_manager_class, digest_str
):
    # Prepare session that will return a row with (id,) for fetchone
    new_id = uuid.uuid4()
    session = fake_session_class(rows=[(new_id,)])
    repo = DocumentRepository(fake_db_manager_class(session))

    # Stable store name for assertions in later tests (not strictly needed here)
    import app.repositories.documents as docrepo_module

    monkeypatch.setattr(
        docrepo_module.settings, 'document_store', 'test-store', raising=True
    )

    data = DocumentCreate(
        collection='default',
        digest=digest_str,
        original_filename='file.pdf',
        content_type='application/pdf',
        size_bytes=123,
        meta={'k': 'v'},
    )

    got_id = await repo.create(data=data)

    # Assertions: an INSERT and a SELECT were executed, commit called once
    assert any('INSERT INTO documents' in sql for sql, _ in session.executed)
    assert any('SELECT id FROM documents' in sql for sql, _ in session.executed)
    assert session.commits == 1
    assert got_id == new_id


@pytest.mark.asyncio
async def test_get_returns_document_model(fake_session_class, fake_db_manager_class):
    # Prepare row matching SELECT order in repository
    doc_id = uuid.uuid4()
    from datetime import datetime

    created_at = datetime.now()
    row = (
        doc_id,  # id
        'default',  # collection
        'b' * 64,  # digest
        'x.pdf',  # original_filename
        'application/pdf',  # content_type
        456,  # size_bytes
        's3://bucket/original',  # original_uri
        's3://bucket/markdown',  # markdown_uri
        {'m': 1},  # meta
        created_at,  # created_at
    )

    session = fake_session_class(rows=[row])
    repo = DocumentRepository(fake_db_manager_class(session))

    doc = await repo.get(id=doc_id)

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
    monkeypatch, fake_session_class, fake_db_manager_class
):
    session = fake_session_class()

    import app.repositories.documents as docrepo_module

    monkeypatch.setattr(
        docrepo_module.settings, 'document_store', 'test-store', raising=True
    )

    repo = DocumentRepository(fake_db_manager_class(session))
    did = uuid.uuid4()
    await repo.update_uris_by_id(
        id=did,
        original_uri='s3://b/o',
        markdown_uri='s3://b/m',
    )

    # Ensure execute was called with params containing our id, store, and URIs
    assert len(session.executed) == 1
    sql, params = session.executed[0]
    assert 'UPDATE documents SET' in sql
    assert params['id'] == did
    assert params['store'] == 'test-store'
    assert params['original_uri'] == 's3://b/o'
    assert params['markdown_uri'] == 's3://b/m'
    assert session.commits == 1


@pytest.mark.asyncio
async def test_update_meta_by_id_updates_meta(
    fake_session_class, fake_db_manager_class
):
    session = fake_session_class()

    repo = DocumentRepository(fake_db_manager_class(session))
    did = uuid.uuid4()
    new_meta = {'company': 'ACME', 'year': 2024}
    await repo.update_metadata(id=did, metadata=new_meta)

    assert len(session.executed) == 1
    sql, params = session.executed[0]
    assert 'UPDATE documents SET meta' in sql
    assert params['id'] == did
    assert params['meta'] == new_meta
    assert session.commits == 1


@pytest.mark.asyncio
async def test_delete_by_id_executes_and_commits(
    fake_session_class, fake_db_manager_class
):
    # Prepare session to simulate a successful DELETE ... RETURNING with one row
    did = uuid.uuid4()
    session = fake_session_class(rows=[(did,)])
    repo = DocumentRepository(fake_db_manager_class(session))

    deleted = await repo.delete(id=did)

    # Assertions
    assert deleted is True
    assert len(session.executed) == 1
    sql, params = session.executed[0]
    assert 'DELETE FROM documents' in sql
    assert 'RETURNING id' in sql
    assert params['id'] == did
    assert session.commits == 1
