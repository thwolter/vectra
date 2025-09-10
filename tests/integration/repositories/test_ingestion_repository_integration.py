import pytest

from app.repositories.factory import get_ingestion_repository
from app.vector.schemas import IngestionVersionInsert


@pytest.mark.integration
@pytest.mark.needs_postgres
@pytest.mark.asyncio
async def test_delete_by_digest_scoped_by_collection(digest_str, another_digest_str):
    repo = get_ingestion_repository()
    await repo.ensure_ingestion_versions_table()

    # Seed two digests across two collections
    insert_rows = [
        IngestionVersionInsert(
            collection='default',
            digest=digest_str,
            chunker_version='cv1',
            embed_model='em',
            embed_model_ver='v1',
        ),
        IngestionVersionInsert(
            collection='financial',
            digest=digest_str,
            chunker_version='cv2',
            embed_model='em',
            embed_model_ver='v1',
        ),
    ]

    for row in insert_rows:
        await repo.insert_Key(row)

    assert await repo.exists_by_digest(digest=digest_str, collection='default') is True
    assert (
        await repo.exists_by_digest(digest=digest_str, collection='financial') is True
    )

    await repo.delete_by_digest(digest=digest_str, collection='default')

    # Verify rows for target digest are gone only in 'default'
    assert await repo.exists_by_digest(digest=digest_str, collection='default') is False
    assert (
        await repo.exists_by_digest(digest=digest_str, collection='financial') is True
    )

    # Deleting again (idempotent) should be a no-op
    await repo.delete_by_digest(digest=digest_str, collection='default')

    # Now delete the other collection and ensure it's removed
    await repo.delete_by_digest(digest=digest_str, collection='financial')
    assert (
        await repo.exists_by_digest(digest=digest_str, collection='financial') is False
    )
