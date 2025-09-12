import pytest

from app.repositories import Ingestion
import uuid


@pytest.mark.asyncio
async def test_check_ingestion_version_exists_true_and_false(
    fake_session_class, digest_str
):
    # True case: simulate scalar present
    session_true = fake_session_class(scalar='some-id')
    from app.vector.schemas import IngestionVersionKey

    key = IngestionVersionKey(
        digest=digest_str,
        collection='col',
        chunker_version='cv',
        embed_model='em',
        embed_model_ver='v1',
    )
    exists = await Ingestion.exists(session_true, key=key)
    assert exists is True

    # False case: scalar None
    session_false = fake_session_class(scalar=None)
    key2 = IngestionVersionKey(
        digest=digest_str,
        collection='col',
        chunker_version='cv',
        embed_model='em',
        embed_model_ver='v1',
    )
    not_exists = await Ingestion.exists(session_false, key=key2)
    assert not_exists is False


@pytest.mark.asyncio
async def test_insert_ingestion_version_executes_insert_with_named_params(
    fake_session_class, digest_str
):
    fake_session = fake_session_class(rows=[(uuid.uuid4(),)])

    from app.vector.schemas import IngestionVersionInsert

    payload = IngestionVersionInsert(
        collection='col',
        digest=digest_str,
        chunker_version='cv',
        embed_model='em',
        embed_model_ver='v1',
    )
    await Ingestion.create(fake_session, key=payload)

    # Should have executed one INSERT with named params and committed
    assert any(
        'INSERT INTO ingestion_versions' in sql for sql, _ in fake_session.executed
    )
    assert fake_session.commits == 1
