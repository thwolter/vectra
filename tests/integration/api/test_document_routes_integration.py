import pytest


@pytest.mark.integration
async def test_get_document_by_id(session, auth_client, document_created):
    res = auth_client.get(f'/api/v1/documents/{document_created.id}')
    assert res.status_code == 200, res.text
    assert res.json()['id'] == str(document_created.id)
