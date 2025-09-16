from __future__ import annotations

from pathlib import Path

import pytest
from loguru import logger

from app.core.config import get_settings


@pytest.fixture(autouse=True)
def _use_tmp_local_store_base(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Redirect LocalFileStore base path to a pytest-provided temp dir.

    Many tests instantiate LocalFileStore indirectly via providers using
    `settings.local_file_path` as the base directory. The default setting points
    at the project-level `documents/`, which causes test runs to create or
    modify files under the repository directory.

    This autouse fixture ensures every test uses an isolated temporary directory
    so no `documents/` folder or files are created at the project root. Tests
    that need a specific path can still pass `base_path=...` explicitly when
    creating `LocalFileStore` instances; this fixture only affects the default
    settings-based path.
    """
    settings = get_settings()
    base = tmp_path / 'documents'
    base.mkdir(parents=True, exist_ok=True)

    # Patch the live settings object so any code calling get_settings() will
    # pick up the temporary path.
    monkeypatch.setattr(settings, 'local_file_path', str(base))
    logger.debug(f'Using temporary local store base path: {base}')

    yield
