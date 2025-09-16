import uuid

import pytest

from app.api.schemas import AccessContext, AuthContext
from app.core.dependencies import (
    access_scoped_session,
    require_access_context,
    require_auth,
)
from app.main import app

# --- test helpers ------------------------------------------------------------


def _fake_auth_ctx() -> AuthContext:
    return AuthContext(
        sub=uuid.UUID('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'),
        tid=uuid.UUID('00000000-0000-0000-0000-000000000001'),
        role='tester',
        scopes=['*'],
    )


async def _fake_get_current_auth():
    return _fake_auth_ctx()


async def _fake_get_access_context():
    a = _fake_auth_ctx()
    return AccessContext(tenant_id=a.tid, user_id=a.sub)


## --- pytest fixtures ---------------------------------------------------------


@pytest.fixture(scope='session')
def anyio_backend():
    return 'asyncio'


# Ensure database is initialized and schema exists for tests
@pytest.fixture(scope='session', autouse=True)
async def _init_db_schema():
    """Initialize DB schema for tests."""
    from app.core.database import DatabaseManager

    db = DatabaseManager()
    await db.initialize()
    await db.ensure_schema()
    try:
        yield
    finally:
        await db.close()


@pytest.fixture(scope='session', autouse=True)
def override_auth_dependencies():
    # Override identity; do not change access_scoped_session
    app.dependency_overrides[require_auth] = _fake_get_current_auth
    app.dependency_overrides[require_access_context] = _fake_get_access_context
    yield
    app.dependency_overrides.clear()


@pytest.fixture
async def session():
    # Provide an explicit AccessContext to the access_scoped_session dependency
    ctx = await _fake_get_access_context()
    async for s in access_scoped_session(tenant=ctx):
        yield s


@pytest.fixture
async def session_another_user():
    ctx = await _fake_get_access_context()
    ctx.user_id = uuid.uuid4()
    async for s in access_scoped_session(tenant=ctx):
        yield s


@pytest.fixture
async def session_another_tenant():
    ctx = await _fake_get_access_context()
    ctx.user_id = uuid.uuid4()
    ctx.tenant_id = uuid.uuid4()
    async for s in access_scoped_session(tenant=ctx):
        yield s
