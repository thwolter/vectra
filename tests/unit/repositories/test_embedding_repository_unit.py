import json
import pytest

from app.repositories.embeddings import EmbeddingsRepository


@pytest.mark.asyncio
async def test_update_document_metadata_noop_on_empty_dict(
    fake_session_class, fake_db_manager_class
):
    session = fake_session_class()
    repo = EmbeddingsRepository(fake_db_manager_class(session))

    await repo.update_metadata('docid', collection='table', metadata={})
    # No DB calls when no metadata to update
    assert session.executed == []


@pytest.mark.asyncio
async def test_update_document_metadata_executes_merge_jsonb(
    fake_session_class, fake_db_manager_class
):
    session = fake_session_class()
    repo = EmbeddingsRepository(fake_db_manager_class(session))

    updates = {'company': 'Apple', 'financial_year': '2024'}
    await repo.update_metadata('doc-1', collection='my_table', metadata=updates)

    assert len(session.executed) == 1
    sql, params = session.executed[0]
    # Assert named params used
    assert params['digest'] == 'doc-1'
    assert json.loads(params['metadata']) == updates
    assert params['collection'] == 'my_table'
    assert "SET cmetadata = COALESCE(e.cmetadata, '{}'::JSONB) ||" in sql


@pytest.mark.asyncio
async def test_check_document_exists_true_and_false(
    fake_session_class, fake_db_manager_class
):
    # True
    session1 = fake_session_class(rows=[(1,)])
    repo1 = EmbeddingsRepository(fake_db_manager_class(session1))
    assert await repo1.exists_by_digest('doc-1', collection='col') is True

    # False
    session2 = fake_session_class(rows=[])
    repo2 = EmbeddingsRepository(fake_db_manager_class(session2))
    assert await repo2.exists_by_digest('doc-1', collection='col') is False
