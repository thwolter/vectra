import json

import pytest

from app.repositories import EmbeddingsRepository


@pytest.fixture
def fake_session_class():
    class FakeSession:
        def __init__(self, *, tenant_id: str, user_id: str) -> None:
            self.info = {'tenant_id': tenant_id, 'user_id': user_id}
            self.executed: list[tuple[str, dict]] = []
            self.commits = 0

        async def exec(self, sql, params=None):
            self.executed.append((str(sql), params or {}))

        async def commit(self):
            self.commits += 1

    return FakeSession


@pytest.fixture
def mock_session(fake_session_class):
    """Fixture providing a FakeSession instance with default empty configuration."""
    return fake_session_class(tenant_id='t-1', user_id='u-1')


async def test_update_document_metadata_noop_on_empty_dict(mock_session):
    await EmbeddingsRepository.update_metadata(mock_session, digest='docid', collection='table', metadata={})
    # No DB calls when no metadata to update
    assert mock_session.executed == []


async def test_update_document_metadata_executes_merge_jsonb(mock_session):
    updates = {'company': 'Apple', 'financial_year': '2024'}
    await EmbeddingsRepository.update_metadata(mock_session, digest='doc-1', collection='my_table', metadata=updates)

    assert len(mock_session.executed) == 1
    sql, params = mock_session.executed[0]
    # Assert named params used
    assert params['digest'] == 'doc-1'
    assert json.loads(params['metadata']) == updates
    assert params['collection'] == 'my_table'
    assert "SET cmetadata = COALESCE(e.cmetadata, '{}'::JSONB) ||" in sql
