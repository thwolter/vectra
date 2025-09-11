from uuid import UUID

import pytest

from app.core.dependencies import get_database_manager
from app.repositories.documents import DocumentRepository
from app.repositories.schemas import DocumentCreate
from app.schemas.enums import CollectionEnum


@pytest.fixture
async def repo() -> DocumentRepository:
    return DocumentRepository(get_database_manager())


@pytest.mark.integration
@pytest.mark.needs_postgres
@pytest.mark.asyncio
async def test_create_and_get_document_roundtrip(repo, session, random_digest):
    data = DocumentCreate(
        collection=CollectionEnum.DEFAULT.value,
        digest=random_digest,
        original_filename='report.pdf',
        content_type='application/pdf',
        size_bytes=12345,
        meta={'hint': 'v1'},
    )

    doc_id = await repo.create(session, data=data)
    assert isinstance(doc_id, UUID)

    doc = await repo.get(session, id=doc_id)
    assert doc.collection == CollectionEnum.DEFAULT.value
    assert doc.digest == random_digest
    assert doc.original_filename == 'report.pdf'
    assert doc.content_type == 'application/pdf'
    assert doc.size_bytes == 12345
    assert doc.meta == {'hint': 'v1'}


@pytest.mark.integration
@pytest.mark.needs_postgres
@pytest.mark.asyncio
async def test_create_is_idempotent_by_collection_and_digest(
    repo: DocumentRepository, session, digest_str
):
    first = DocumentCreate(
        collection=CollectionEnum.FINANCIAL.value,
        digest=digest_str,
        original_filename='first.pdf',
        content_type='application/pdf',
        size_bytes=10,
    )
    second = DocumentCreate(
        collection=CollectionEnum.FINANCIAL.value,
        digest=digest_str,
        original_filename='second.pdf',  # should be ignored due to first-seen wins
        content_type='application/pdf',
        size_bytes=20,
    )

    id1 = await repo.create(session, data=first)
    id2 = await repo.create(session, data=second)

    assert id1 == id2, 'Same (collection,digest) should return existing row id'

    # Ensure original_filename is from the first insert (first-seen wins)
    doc = await repo.get(session, id=id1)
    assert doc.original_filename == 'first.pdf'


@pytest.mark.integration
@pytest.mark.needs_postgres
@pytest.mark.asyncio
async def test_same_digest_in_different_collections_creates_distinct_rows(
    repo,
    session,
    digest_str,
):
    id_default = await repo.create(
        session,
        data=DocumentCreate(
            collection=CollectionEnum.DEFAULT.value,
            digest=digest_str,
            original_filename='a.pdf',
        ),
    )
    id_fin = await repo.create(
        session,
        data=DocumentCreate(
            collection=CollectionEnum.FINANCIAL.value,
            digest=digest_str,
            original_filename='a.pdf',
        ),
    )

    assert id_default != id_fin


@pytest.mark.integration
@pytest.mark.needs_postgres
@pytest.mark.asyncio
async def test_update_uris_updates_fields(repo, session, random_digest):
    doc_id = await repo.create(
        session,
        data=DocumentCreate(
            collection=CollectionEnum.DEFAULT.value,
            digest=random_digest,
            original_filename='x.pdf',
        ),
    )

    await repo.update_uris_by_id(
        session,
        id=doc_id,
        original_uri='s3://bucket/path/original.pdf',
        markdown_uri='s3://bucket/path/document.md',
    )

    doc = await repo.get(session, id=doc_id)
    assert doc.original_uri == 's3://bucket/path/original.pdf'
    assert doc.markdown_uri == 's3://bucket/path/document.md'


@pytest.mark.integration
@pytest.mark.needs_postgres
@pytest.mark.asyncio
async def test_update_metadata_replaces_meta(repo, session, random_digest):
    doc_id = await repo.create(
        session,
        data=DocumentCreate(
            collection=CollectionEnum.DEFAULT.value,
            digest=random_digest,
            original_filename='y.pdf',
            meta={'keep': 'no'},
        ),
    )

    await repo.update_metadata(
        session,
        id=doc_id,
        metadata={'company': 'Acme', 'year': 2024},
        replace=True,
    )
    doc = await repo.get(session, id=doc_id)
    assert doc.meta == {'company': 'Acme', 'year': 2024}

    await repo.update_metadata(
        session, id=doc_id, metadata={'another': 'new'}, replace=False
    )
    doc = await repo.get(session, id=doc_id)
    assert doc.meta == {'company': 'Acme', 'year': 2024, 'another': 'new'}


@pytest.mark.integration
@pytest.mark.needs_postgres
@pytest.mark.asyncio
async def test_delete_removes_row_and_is_idempotent(repo, session, random_digest):
    doc_id = await repo.create(
        session,
        data=DocumentCreate(
            collection=CollectionEnum.DEFAULT.value,
            digest=random_digest,
            original_filename='z.pdf',
        ),
    )

    # First delete returns True and subsequent get should fail
    first = await repo.delete(session, id=doc_id)
    assert first is True
    with pytest.raises(RuntimeError):
        await repo.get(session, id=doc_id)

    # Second delete returns False (no-op)
    second = await repo.delete(session, id=doc_id)
    assert second is False
