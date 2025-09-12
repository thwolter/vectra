from uuid import UUID

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from app.api.v1 import ROUTERS
from app.api.schemas import AuthContext
from app.core.dependencies import require_auth, access_scoped_session


@pytest.fixture()
def fake_auth_client() -> TestClient:
    app = FastAPI()
    for router, prefix in ROUTERS:
        app.include_router(router, prefix=prefix)

    app.dependency_overrides[access_scoped_session] = lambda: object()
    app.dependency_overrides[require_auth] = lambda: AuthContext(
        sub=UUID('00000000-0000-0000-0000-000000000001'),
        tid=UUID('00000000-0000-0000-0000-000000000042'),
        role='owner',
        scopes=['uploads:write', 'jobs:read'],
    )

    return TestClient(app)
