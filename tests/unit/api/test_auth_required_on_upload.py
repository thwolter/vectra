import io
import pytest
from starlette.testclient import TestClient

from app.main import app
from app.core.dependencies import require_auth, require_access_context


@pytest.fixture()
def unauth_client():
    # Temporarily remove auth overrides to test real auth requirement
    saved_auth = app.dependency_overrides.pop(require_auth, None)
    saved_access = app.dependency_overrides.pop(require_access_context, None)
    try:
        yield TestClient(app)
    finally:
        # Restore overrides so other tests remain unaffected
        if saved_auth is not None:
            app.dependency_overrides[require_auth] = saved_auth
        if saved_access is not None:
            app.dependency_overrides[require_access_context] = saved_access


def test_upload_requires_authorization_header(unauth_client: TestClient):
    # Provide a minimal, valid-looking PDF upload so parsing succeeds up to auth check
    files = {
        'file': ('empty.pdf', io.BytesIO(b'%PDF-1.4\n%%EOF\n'), 'application/pdf'),
    }
    r = unauth_client.post('/api/v1/uploads', files=files)
    assert r.status_code == 401
    assert 'Authorization' in (r.json().get('detail', '') or 'Authorization')
