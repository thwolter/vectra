import base64
import os
from uuid import UUID

import pytest

from app.core.dependencies import get_database_manager
from app.repositories.documents import DocumentRepository
from app.repositories.schemas import DocumentCreate
from app.schemas.enums import CollectionEnum


@pytest.fixture
async def repo() -> DocumentRepository:
    return DocumentRepository(get_database_manager())


def _random_sha256_b64() -> str:
    # 32 bytes -> standard base64 with '=' padding => 44 chars
    return base64.b64encode(os.urandom(32)).decode('ascii')


@pytest.mark.integration
@pytest.mark.needs_postgres
@pytest.mark.asyncio
async def test_create_and_get_document_roundtrip(repo: DocumentRepository):
    digest = _random_sha256_b64()
    data = DocumentCreate(
        collection=CollectionEnum.DEFAULT.value,
        digest=digest,
        original_filename='report.pdf',
        content_type='application/pdf',
        size_bytes=12345,
        meta={'hint': 'v1'},
    )

    doc_id = await repo.create(data)
    assert isinstance(doc_id, UUID)

    doc = await repo.get(id=doc_id)
    assert doc.collection == CollectionEnum.DEFAULT.value
    assert doc.digest == digest
    assert doc.original_filename == 'report.pdf'
    assert doc.content_type == 'application/pdf'
    assert doc.size_bytes == 12345
    assert doc.meta == {'hint': 'v1'}


@pytest.mark.integration
@pytest.mark.needs_postgres
@pytest.mark.asyncio
async def test_create_is_idempotent_by_collection_and_digest(repo: DocumentRepository):
    digest = _random_sha256_b64()

    first = DocumentCreate(
        collection=CollectionEnum.FINANCIAL.value,
        digest=digest,
        original_filename='first.pdf',
        content_type='application/pdf',
        size_bytes=10,
    )
    second = DocumentCreate(
        collection=CollectionEnum.FINANCIAL.value,
        digest=digest,
        original_filename='second.pdf',  # should be ignored due to first-seen wins
        content_type='application/pdf',
        size_bytes=20,
    )

    id1 = await repo.create(first)
    id2 = await repo.create(second)

    assert id1 == id2, 'Same (collection,digest) should return existing row id'

    # Ensure original_filename is from the first insert (first-seen wins)
    doc = await repo.get(id=id1)
    assert doc.original_filename == 'first.pdf'


@pytest.mark.integration
@pytest.mark.needs_postgres
@pytest.mark.asyncio
async def test_same_digest_in_different_collections_creates_distinct_rows(
    repo: DocumentRepository,
):
    digest = _random_sha256_b64()

    id_default = await repo.create(
        DocumentCreate(
            collection=CollectionEnum.DEFAULT.value,
            digest=digest,
            original_filename='a.pdf',
        )
    )
    id_fin = await repo.create(
        DocumentCreate(
            collection=CollectionEnum.FINANCIAL.value,
            digest=digest,
            original_filename='a.pdf',
        )
    )

    assert id_default != id_fin


@pytest.mark.integration
@pytest.mark.needs_postgres
@pytest.mark.asyncio
async def test_update_uris_updates_fields(repo: DocumentRepository):
    digest = _random_sha256_b64()
    doc_id = await repo.create(
        DocumentCreate(
            collection=CollectionEnum.DEFAULT.value,
            digest=digest,
            original_filename='x.pdf',
        )
    )

    await repo.update_uris_by_id(
        id=doc_id,
        original_uri='s3://bucket/path/original.pdf',
        markdown_uri='s3://bucket/path/document.md',
    )

    doc = await repo.get(id=doc_id)
    assert doc.original_uri == 's3://bucket/path/original.pdf'
    assert doc.markdown_uri == 's3://bucket/path/document.md'


@pytest.mark.integration
@pytest.mark.needs_postgres
@pytest.mark.asyncio
async def test_update_metadata_replaces_meta(repo: DocumentRepository):
    digest = _random_sha256_b64()
    doc_id = await repo.create(
        DocumentCreate(
            collection=CollectionEnum.DEFAULT.value,
            digest=digest,
            original_filename='y.pdf',
            meta={'keep': 'no'},
        )
    )

    await repo.update_metadata(
        id=doc_id, metadata={'company': 'Acme', 'year': 2024}, replace=True
    )
    doc = await repo.get(id=doc_id)
    assert doc.meta == {'company': 'Acme', 'year': 2024}

    await repo.update_metadata(id=doc_id, metadata={'another': 'new'}, replace=False)
    doc = await repo.get(id=doc_id)
    assert doc.meta == {'company': 'Acme', 'year': 2024, 'another': 'new'}


@pytest.mark.integration
@pytest.mark.needs_postgres
@pytest.mark.asyncio
async def test_delete_removes_row_and_is_idempotent(repo: DocumentRepository):
    digest = _random_sha256_b64()
    doc_id = await repo.create(
        DocumentCreate(
            collection=CollectionEnum.DEFAULT.value,
            digest=digest,
            original_filename='z.pdf',
        )
    )

    # First delete returns True and subsequent get should fail
    first = await repo.delete(id=doc_id)
    assert first is True
    with pytest.raises(RuntimeError):
        await repo.get(id=doc_id)

    # Second delete returns False (no-op)
    second = await repo.delete(id=doc_id)
    assert second is False
