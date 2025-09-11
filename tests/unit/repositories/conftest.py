import pytest


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
