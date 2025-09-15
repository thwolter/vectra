import pytest
import pickle
import sys
from pathlib import Path
from typing import List, TYPE_CHECKING

from langchain_core.documents import Document

# Load session-level fixtures (auth, tenant, httpx client) for all tests
pytest_plugins = [
    'tests.fixtures.session',
    'tests.fixtures.client',
    'tests.fixtures.vector',
    'tests.fixtures.jobs',
    'tests.fixtures.digest',
    'tests.fixtures.data',
    'tests.fixtures.store',
]

if TYPE_CHECKING:
    pass

# Minimal path setup: ensure project root is on sys.path for absolute imports like `from app...`
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_PROJECT_ROOT_STR = str(_PROJECT_ROOT)
if _PROJECT_ROOT_STR not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT_STR)


def pytest_ignore_collect(path, config):
    """Avoid importing tests under integration/ and e2e/ unless explicitly requested.

    This prevents import-time errors from modules that rely on optional deps or
    environment when running only unit tests.
    """
    path_str = str(path)
    selected = config.getoption('-m') or ''
    if '/integration/' in path_str or path_str.endswith('/integration'):
        return 'integration' not in selected
    if '/e2e/' in path_str or path_str.endswith('/e2e'):
        return 'e2e' not in selected
    return False


def pytest_collection_modifyitems(config, items):
    if config.getoption('-m') and 'e2e' in config.getoption('-m'):
        pass
    else:
        skip_e2e = pytest.mark.skip(reason='need -m e2e to run')
        for item in items:
            if 'e2e' in item.keywords:
                item.add_marker(skip_e2e)

    if config.getoption('-m') and 'integration' in config.getoption('-m'):
        pass
    else:
        skip_integration = pytest.mark.skip(reason='need -m integration to run')
        for item in items:
            if 'integration' in item.keywords:
                item.add_marker(skip_integration)


@pytest.fixture
def sample_documents() -> List[Document]:
    """Load sample documents from pickle file."""
    sample_path = Path(__file__).parents[0] / 'data' / 'sample_docs.pkl'
    with open(sample_path, 'rb') as f:
        return pickle.load(f)


def pytest_runtest_setup(item: pytest.Item):
    """Skip tests with needs_* markers when required environment vars are missing.

    This provides explicit gating without any custom requires_env plumbing.
    Use at test level, e.g., pytestmark = [pytest.mark.integration, pytest.mark.needs_postgres].
    """
    import os

    def _missing(vars_: list[str]) -> list[str]:
        return [v for v in vars_ if not os.environ.get(v)]

    if item.get_closest_marker('needs_postgres'):
        missing = _missing(['POSTGRES_URL'])
        if missing:
            pytest.skip(f'skipped: missing env vars for Postgres: {", ".join(missing)}')

    if item.get_closest_marker('needs_aws'):
        missing = _missing(
            ['AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY', 'AWS_S3_BUCKET']
        )
        if missing:
            pytest.skip(f'skipped: missing env vars for AWS/S3: {", ".join(missing)}')

    if item.get_closest_marker('needs_openai'):
        missing = _missing(['OPENAI_API_KEY'])
        if missing:
            pytest.skip(f'skipped: missing env vars for OpenAI: {", ".join(missing)}')
