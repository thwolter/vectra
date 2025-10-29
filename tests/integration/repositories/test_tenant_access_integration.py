import pytest

from repositories import document_repository
from repositories.exceptions import RecordNotFoundError


@pytest.mark.needs_postgres
async def test_cross_tenant_access_is_isolated(document_created, session_another_tenant):
    with pytest.raises(RecordNotFoundError):
        await document_repository.get(session_another_tenant, document_id=document_created.id)


@pytest.mark.needs_postgres
async def test_same_tenant_different_users_can_access(document_created, session_another_user):
    doc = await document_repository.get(session_another_user, document_id=document_created.id)
    assert doc is not None
