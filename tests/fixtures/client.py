import pytest
from starlette.testclient import TestClient

from app.main import app as main_app


@pytest.fixture()
def auth_client() -> TestClient:
    # Use the real application instance so session-wide dependency overrides
    # from tests/fixtures/session.py apply uniformly across tests.
    return TestClient(main_app)
