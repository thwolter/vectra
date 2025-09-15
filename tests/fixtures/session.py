import uuid

import pytest
from app.main import app
from app.api.schemas import AuthContext, AccessContext
from app.core.dependencies import (
    require_auth,
    require_access_context,
    access_scoped_session,
)


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


## --- pytest fixtures [Unit tests] --------------------------------------------


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

        # Added to match SQLAlchemy Result API used by repositories
        def scalar(self):
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
    class _FakeResult:
        def __init__(self, rows=None, scalar_value=None):
            self._rows = rows or []
            self._scalar = scalar_value

        def scalar(self):
            return self._scalar

        def scalar_one_or_none(self):
            return self._scalar

        class _Mappings:
            def __init__(self, rows):
                self._rows = rows or []

            def all(self):
                return list(self._rows)

        def mappings(self):
            return _FakeResult._Mappings(self._rows)

    class FakeSession:
        """Minimal async session double for repository tests."""

        def __init__(
            self,
            *,
            tenant_id: str | None = None,
            user_id: str | None = None,
            result_rows: list[dict] | None = None,
            result_scalar: object | None = None,
            get_exists: bool = False,
            orm_exists: bool | None = None,
        ) -> None:
            self.info = {'tenant_id': tenant_id, 'user_id': user_id}
            self._rows = result_rows
            self._scalar = result_scalar
            # Maintain backward-compat param name expected by some unit tests
            self._get_exists = orm_exists if orm_exists is not None else get_exists

            # Optional counters (keep legacy names used in some tests)
            self.commits = 0
            self.rollbacks = 0
            self.add_calls = 0
            self.delete_calls = 0
            self.adds = 0
            self.deletes = 0
            self.gets = 0
            self.executed: list[tuple[str, dict]] = []
            self._deleted_obj = None

        def add(self, obj):  # noqa: ANN001 parity with AsyncSession.add
            self.add_calls += 1
            self.adds += 1

        async def get(self, model, obj_id):  # noqa: ANN001 parity with AsyncSession.get
            self.gets += 1
            return object() if self._get_exists else None

        async def delete(self, obj):  # noqa: ANN001 parity with AsyncSession.delete
            self.delete_calls += 1
            self.deletes += 1
            self._deleted_obj = obj

        async def execute(self, sql, params=None):
            self.executed.append((str(sql), params or {}))
            return _FakeResult(rows=self._rows, scalar_value=self._scalar)

        async def commit(self):
            self.commits += 1

        async def rollback(self):
            self.rollbacks += 1

        async def close(self):
            return None

    return FakeSession


@pytest.fixture
def mock_session(fake_session_class):
    """Fixture providing a FakeSession instance with default empty configuration."""
    return fake_session_class(tenant_id='t-1', user_id='u-1')
