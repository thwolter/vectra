import pytest


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

    return FakeResult


@pytest.fixture
def fake_session_class(fake_result_class):
    """Fixture providing a FakeSession class for database testing.

    This class mocks database sessions with tracking for executed SQL and commits.
    """

    class FakeSession:
        def __init__(self, rows=None, scalar=None):
            self.executed = []  # list of (sql, params)
            self._rows = rows
            self._scalar = scalar
            self.commits = 0

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
def fake_acquire_class():
    """Fixture providing a FakeAcquire class for database testing.

    This class mocks the async context manager for database session acquisition.
    """

    class FakeAcquire:
        def __init__(self, session):
            self.session = session

        async def __aenter__(self):
            return self.session

        async def __aexit__(self, exc_type, exc, tb):
            return False

    return FakeAcquire


@pytest.fixture
def fake_db_manager_class(fake_acquire_class):
    """Fixture providing a FakeDBManager class for database testing.

    This class mocks the database manager with session handling and schema management.
    """

    class FakeDBManager:
        def __init__(self, session):
            self._session = session
            self.is_initialized = True
            self.ensure_calls = 0

        async def initialize(self):
            self.is_initialized = True

        async def ensure_schema(self):
            self.ensure_calls += 1
            return None

        def get_session(self):
            return fake_acquire_class(self._session)

    return FakeDBManager


# Factory fixtures for common test scenarios


@pytest.fixture
def fake_session(fake_session_class):
    """Fixture providing a FakeSession instance with default empty configuration."""
    return fake_session_class()


@pytest.fixture
def fake_session_with_scalar(fake_session_class):
    """Fixture providing a FakeSession instance with a scalar value."""
    return fake_session_class(scalar='some-id')


@pytest.fixture
def fake_session_with_rows(fake_session_class, request):
    """Fixture providing a FakeSession instance with configurable rows.

    Usage: @pytest.mark.parametrize('fake_session_with_rows', [[(1,), (2,)]], indirect=True)
    """
    rows = request.param if hasattr(request, 'param') else []
    return fake_session_class(rows=rows)


@pytest.fixture
def fake_db_manager(fake_db_manager_class, fake_session):
    """Fixture providing a FakeDBManager instance with a default session."""
    return fake_db_manager_class(fake_session)
