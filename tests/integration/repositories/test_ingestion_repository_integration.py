import pytest

from app.vector.schemas import IngestionVersionInsert
from app.repositories.ingestion_repository import Ingestion


@pytest.mark.integration
@pytest.mark.needs_postgres
@pytest.mark.asyncio
async def test_delete_by_digest_scoped_by_collection(
    random_digest, another_digest_str, session
):
    # Seed two digests across two collections
    insert_rows = [
        IngestionVersionInsert(
            collection='default',
            digest=random_digest,
            chunker_version='cv1',
            embed_model='em',
            embed_model_ver='v1',
        ),
        IngestionVersionInsert(
            collection='financial',
            digest=random_digest,
            chunker_version='cv2',
            embed_model='em',
            embed_model_ver='v1',
        ),
    ]

    for row in insert_rows:
        await Ingestion.create(session, key=row)

    exists_default = await Ingestion.exists(
        session, digest=random_digest, collection='default'
    )
    exists_financial = await Ingestion.exists(
        session, digest=random_digest, collection='financial'
    )
    assert exists_default is True
    assert exists_financial is True

    await Ingestion.delete(session, digest=random_digest, collection='default')

    exists_default = await Ingestion.exists(
        session, digest=random_digest, collection='default'
    )
    exists_financial = await Ingestion.exists(
        session, digest=random_digest, collection='financial'
    )
    assert exists_default is False
    assert exists_financial is False

    # Deleting again (idempotent) should be a no-op
    await Ingestion.delete(session, digest=random_digest, collection='default')

    # Now delete the other collection and ensure it's removed
    await Ingestion.delete(session, digest=random_digest, collection='financial')
    exists = await Ingestion.exists(
        session, digest=random_digest, collection='financial'
    )
    assert exists is False
