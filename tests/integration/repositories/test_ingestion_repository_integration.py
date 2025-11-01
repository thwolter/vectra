from uuid import uuid4

import pytest

from repositories import ingestion_repository
from repositories.exceptions import RecordNotFoundError
from repositories.schemas import IngestionCreate, IngestionVersion


async def test_can_create_ingestion(auth_session, ingestion_created):
    result = await ingestion_repository.get(auth_session, ingestion_id=ingestion_created.id)
    assert ingestion_created is not None
    assert result.id == ingestion_created.id


async def test_get_nonexistent_raises(auth_session):
    with pytest.raises(RecordNotFoundError):
        await ingestion_repository.get(auth_session, ingestion_id=uuid4())


async def test_exists_true_when_present(auth_session, ingestion_created):
    version = IngestionVersion(
        collection=ingestion_created.collection,
        parser_fp=ingestion_created.parser_fp,
        chunker_fp=ingestion_created.chunker_fp,
        embedding_fp=ingestion_created.embedding_fp,
    )
    assert (
        await ingestion_repository.exists(
            auth_session,
            collection=ingestion_created.collection,
            digest=ingestion_created.digest,
            version=version,
        )
        is True
    )


async def test_exists_false_when_absent(auth_session, digest_random):
    version = IngestionVersion.from_settings(collection='default')
    assert (
        await ingestion_repository.exists(
            auth_session,
            collection='default',
            digest=digest_random,
            version=version,
        )
        is False
    )


async def test_delete_returns_true_then_false(auth_session, job_created, digest_random):
    # Create a dedicated ingestion record for this test
    ingestion_create = IngestionCreate.create(
        collection='default',
        document_id=job_created.document_id,
        job_id=job_created.id,
        digest=digest_random,
    )
    rec = await ingestion_repository.create(auth_session, data=ingestion_create)

    # First delete should succeed
    ok = await ingestion_repository.delete(auth_session, ingestion_id=rec.id)
    assert ok is True

    # Deleting again should return False (record no longer exists)
    ok2 = await ingestion_repository.delete(auth_session, ingestion_id=rec.id)
    assert ok2 is False
