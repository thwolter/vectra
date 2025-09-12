import json
import pytest

from app.repositories import Embeddings


@pytest.mark.asyncio
async def test_update_document_metadata_noop_on_empty_dict(mock_session):
    await Embeddings.update_metadata(
        mock_session, digest='docid', collection='table', metadata={}
    )
    # No DB calls when no metadata to update
    assert mock_session.executed == []


@pytest.mark.asyncio
async def test_update_document_metadata_executes_merge_jsonb(mock_session):
    updates = {'company': 'Apple', 'financial_year': '2024'}
    await Embeddings.update_metadata(
        mock_session, digest='doc-1', collection='my_table', metadata=updates
    )

    assert len(mock_session.executed) == 1
    sql, params = mock_session.executed[0]
    # Assert named params used
    assert params['digest'] == 'doc-1'
    assert json.loads(params['metadata']) == updates
    assert params['collection'] == 'my_table'
    assert "SET cmetadata = COALESCE(e.cmetadata, '{}'::JSONB) ||" in sql
