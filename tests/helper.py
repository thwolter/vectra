from __future__ import annotations

import io
from pathlib import Path
from typing import Any

from starlette.testclient import TestClient

from app.main import app
from app.profiles.registry import register_profile
from app.schemas.enums import CollectionEnum
from app.services.factory import get_upload_service as _get_upload_service_dep
from tests.support.profiles import build_test_profile


def make_files_param(apple_report_first_page):
    pdf = apple_report_first_page
    assert pdf.exists(), f'Test PDF not found at {pdf}'
    with open(pdf, 'rb') as f:
        files = {'file': (pdf.name, io.BytesIO(f.read()), 'application/pdf')}
    return files


class TestClientWithCleanup(TestClient):
    """TestClient subclass that carries a typed cleanup attribute.

    Tests can set `client._cleanup = callable` without mypy/pyright errors.
    """

    _cleanup: callable  # type: ignore[assignment]

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)


def make_client_financial(base_path: Path) -> TestClientWithCleanup:
    profile = build_test_profile(
        name='test_financial',
        collection=CollectionEnum.FINANCIAL.value,
        sample_path=base_path / 'sample_docs.pkl' if (base_path / 'sample_docs.pkl').exists() else None,
    )
    register_profile(profile)

    def _finalizer():
        app.dependency_overrides.pop(_get_upload_service_dep, None)

    app.dependency_overrides[_get_upload_service_dep] = lambda: _get_upload_service_dep(profile_name=profile.name)
    client = TestClientWithCleanup(app)
    client._cleanup = _finalizer  # attach for manual cleanup
    return client
