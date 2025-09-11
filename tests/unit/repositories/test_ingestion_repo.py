import pytest

from app.repositories.ingestion_repository import IngestionVersions
import uuid


@pytest.mark.asyncio
async def test_check_ingestion_version_exists_true_and_false(
    fake_session_class, fake_db_manager_class, digest_str
):
    # True case: simulate scalar present
    session_true = fake_session_class(scalar='some-id')
    repo_true = IngestionVersions(fake_db_manager_class(session_true))
    from app.vector.schemas import IngestionVersionKey

    key = IngestionVersionKey(
        digest=digest_str,
        collection='col',
        chunker_version='cv',
        embed_model='em',
        embed_model_ver='v1',
    )
    exists = await repo_true.exists_by_key(session_true, key=key)
    assert exists is True

    # False case: scalar None
    session_false = fake_session_class(scalar=None)
    repo_false = IngestionVersions(fake_db_manager_class(session_false))
    key2 = IngestionVersionKey(
        digest=digest_str,
        collection='col',
        chunker_version='cv',
        embed_model='em',
        embed_model_ver='v1',
    )
    not_exists = await repo_false.exists_by_key(session_false, key=key2)
    assert not_exists is False


@pytest.mark.asyncio
async def test_insert_ingestion_version_executes_insert_with_named_params(
    fake_session_class, fake_db_manager_class, digest_str
):
    fake_session = fake_session_class(rows=[(uuid.uuid4(),)])
    repo = IngestionVersions(fake_db_manager_class(fake_session))

    from app.vector.schemas import IngestionVersionInsert

    payload = IngestionVersionInsert(
        collection='col',
        digest=digest_str,
        chunker_version='cv',
        embed_model='em',
        embed_model_ver='v1',
    )
    await repo.insert_key(fake_session, key=payload)

    # Should have executed one INSERT with named params and committed
    assert any(
        'INSERT INTO ingestion_versions' in sql for sql, _ in fake_session.executed
    )
    assert fake_session.commits == 1
