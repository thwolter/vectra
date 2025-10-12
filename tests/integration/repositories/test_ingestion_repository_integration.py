from uuid import uuid4

import pytest

from app.repositories import ingestion_repository
from app.repositories.exceptions import RecordNotFoundError
from app.repositories.schemas import IngestionCreate


@pytest.mark.needs_postgres
async def test_can_create_ingestion(session, ingestion_created):
    result = await ingestion_repository.get(session, ingestion_id=ingestion_created.id)
    assert ingestion_created is not None
    assert result.id == ingestion_created.id


@pytest.mark.needs_postgres
async def test_get_nonexistent_raises(session):
    with pytest.raises(RecordNotFoundError):
        await ingestion_repository.get(session, ingestion_id=uuid4())


@pytest.mark.needs_postgres
async def test_exists_true_when_present(session, ingestion_created):
    assert (
        await ingestion_repository.exists(
            session,
            fingerprint=ingestion_created.fingerprint,
            collection=ingestion_created.collection,
            digest=ingestion_created.digest,
        )
        is True
    )


@pytest.mark.needs_postgres
async def test_exists_false_when_absent(session, digest_random):
    assert (
        await ingestion_repository.exists(
            session,
            fingerprint='',
            collection='default',
            digest=digest_random,
        )
        is False
    )


@pytest.mark.needs_postgres
async def test_delete_returns_true_then_false(session, job_created, digest_random):
    # Create a dedicated ingestion record for this test
    ingestion_create = IngestionCreate.create(
        collection='default',
        document_id=job_created.document_id,
        job_id=job_created.id,
        digest=digest_random,
    )
    rec = await ingestion_repository.create(session, data=ingestion_create)

    # First delete should succeed
    ok = await ingestion_repository.delete(session, ingestion_id=rec.id)
    assert ok is True

    # Deleting again should return False (record no longer exists)
    ok2 = await ingestion_repository.delete(session, ingestion_id=rec.id)
    assert ok2 is False
