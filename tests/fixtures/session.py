import os
import uuid
from pathlib import Path

import pytest
from dotenv import dotenv_values
from tenauth.schemas import AccessContext, AuthContext

from alembic import command
from alembic.config import Config
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


def _resolve_test_db_url() -> str:
    env_url = os.getenv('ALEMBIC_DATABASE_URL')
    if env_url:
        return env_url

    project_root = Path(__file__).resolve().parents[2]
    for candidate in (project_root / '.env.migration', project_root / '.env'):
        if candidate.exists():
            values = dotenv_values(candidate)
            url = values.get('ALEMBIC_DATABASE_URL')
            if url:
                return url

    raise RuntimeError(
        'ALEMBIC_DATABASE_URL must be set in the environment or .env/.env.migration for test migrations.'
    )


## --- pytest fixtures ---------------------------------------------------------


@pytest.fixture(scope='session')
def anyio_backend():
    return 'asyncio'


# Ensure database is initialized and schema exists for tests
@pytest.fixture(scope='session', autouse=True)
async def _init_db_schema():
    """Initialize DB schema for tests."""
    test_db_url = _resolve_test_db_url()
    os.environ['ALEMBIC_DATABASE_URL'] = test_db_url

    project_root = Path(__file__).resolve().parents[2]
    alembic_cfg = Config(str((project_root / 'alembic.ini').resolve()))
    # Ensure script_location resolves correctly regardless of CWD
    alembic_cfg.set_main_option('script_location', str((project_root / 'alembic').resolve()))

    # Avoid concurrent Alembic upgrades when running with pytest-xdist
    worker = os.getenv('PYTEST_XDIST_WORKER')
    if worker in (None, 'master', 'gw0'):
        # Single leader performs migrations
        command.upgrade(alembic_cfg, 'head')
    else:
        # Followers wait until schema is ready
        import asyncio as _asyncio

        from app.core.database import DatabaseManager as _DB

        _db_wait = _DB()
        for _ in range(120):  # up to ~60s
            try:
                await _db_wait.initialize()
                await _db_wait.ensure_schema()
                break
            except Exception:
                await _db_wait.close()
                await _asyncio.sleep(0.5)
        else:
            raise RuntimeError('Timed out waiting for schema to be initialized by primary worker')
        await _db_wait.close()

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
