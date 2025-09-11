import uuid
from types import SimpleNamespace

import pytest
from app.main import app
from app.api.schemas import AuthContext, TenantContext
from app.core.dependencies import (
    get_current_auth,
    get_current_tenant,
    tenant_scoped_session,
)
from sqlalchemy import text


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


async def _fake_get_current_tenant():
    a = _fake_auth_ctx()
    return TenantContext(tenant_id=a.tid, user_id=a.sub)


# Ensure RLS is set for DB operations inside requests/background tasks
async def _fake_tenant_scoped_session():
    from app.core.database import DatabaseManager

    db = DatabaseManager()
    async with db.get_session() as session:  # AsyncSession
        await session.execute(
            text("SELECT set_config('app.tenant_id', :tid, false)"),
            {'tid': str(_fake_auth_ctx().tid)},
        )
        from types import SimpleNamespace

        info_ns = SimpleNamespace(
            tenant_id=_fake_auth_ctx().tid,
            user_id=_fake_auth_ctx().sub,
        )

        class _SessionProxy:
            def __init__(self, s, info):
                self._s = s
                self.info = info

            def __getattr__(self, name):
                return getattr(self._s, name)

        yield _SessionProxy(session, info_ns)


# --- pytest fixtures ---------------------------------------------------------


@pytest.fixture(scope='session')
def anyio_backend():
    return 'asyncio'


@pytest.fixture(scope='session', autouse=True)
def _override_dependencies():
    app.dependency_overrides[get_current_auth] = _fake_get_current_auth
    app.dependency_overrides[get_current_tenant] = _fake_get_current_tenant
    app.dependency_overrides[tenant_scoped_session] = _fake_tenant_scoped_session
    yield
    app.dependency_overrides.clear()


# Provide a raw AsyncSession for tests that need direct DB access (e.g., ingestor.delete_embeddings)
@pytest.fixture
async def session():
    from app.core.database import DatabaseManager

    db = DatabaseManager()
    async with db.get_session() as s:  # AsyncSession
        # Set tenant RLS for the session to match test overrides
        await s.execute(
            text("SELECT set_config('app.tenant_id', :tid, false)"),
            {'tid': str(_fake_auth_ctx().tid)},
        )
        # Provide attribute-style access expected by repositories (session.info.user_id)
        from types import SimpleNamespace

        info_ns = SimpleNamespace(
            tenant_id=_fake_auth_ctx().tid,
            user_id=_fake_auth_ctx().sub,
        )

        class _SessionProxy:
            def __init__(self, s, info):
                self._s = s
                self.info = info

            def __getattr__(self, name):
                return getattr(self._s, name)

        yield _SessionProxy(s, info_ns)


@pytest.fixture
def fake_result_class():
    """Fixture providing a FakeResult class for database testing.

    This class mocks database result objects with configurable rows and scalar values.
    """

    class FakeResult:
        def __init__(self, rows=None, scalar=None):
            self._rows = rows or []
            self._scalar = scalar

        def fetchall(self):
            return self._rows

        def fetchone(self):
            return self._rows[0] if self._rows else None

        def scalar_one_or_none(self):
            return self._scalar

        @property
        def rowcount(self):
            return len(self._rows)

        # Provide a minimal .mappings() API compatible with SQLAlchemy's MappingResult
        def mappings(self):
            class _MappingResult:
                def __init__(self, rows):
                    self._rows = rows

                def first(self):
                    # Expect dict rows; if tuple is given, return None (no mapping)
                    if not self._rows:
                        return None
                    row0 = self._rows[0]
                    return row0 if isinstance(row0, dict) else None

            return _MappingResult(self._rows)

    return FakeResult


@pytest.fixture
async def fake_session_class(fake_result_class):
    class FakeSession:
        def __init__(self, rows=None, scalar=None):
            self.executed = []  # list of (sql, params)
            self._rows = rows
            self._scalar = scalar
            self.commits = 0
            self.info = SimpleNamespace(tenant_id=None, user_id=None)

        async def execute(self, sql, params=None):
            self.executed.append((' '.join(str(sql).split()), params or {}))
            return fake_result_class(self._rows, self._scalar)

        async def close(self):
            return None

        async def commit(self):
            self.commits += 1

        async def rollback(self):
            self.executed.clear()
            self.commits = 0

    return FakeSession


@pytest.fixture
def mock_session(fake_session_class):
    """Fixture providing a FakeSession instance with default empty configuration."""
    return fake_session_class()
