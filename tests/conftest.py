from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

# Load session-level fixtures (auth, client, data) for all tests
pytest_plugins = [
    'tests.fixtures.jobs',
    'tests.fixtures.digest',
    'tests.fixtures.data',
    'tests.fixtures.store',
    'tests.fixtures.document',
    'tests.fixtures.ingestion',
]

if TYPE_CHECKING:
    pass


PROJECT_ROOT = Path(__file__).resolve().parent.parent
TESTS_ROOT = Path(__file__).resolve().parent


DEFAULT_ENV_VARS = {
    'OPENAI_API_KEY': 'test-key',
    'JWT_SECRET': 'test-secret',
    'ENV': 'testing',
    'DOCUMENT_STORE': 'local',
}


def pytest_ignore_collect(path, config):
    path_str = str(path)
    selected = config.getoption('-m') or ''
    if '/integration/' in path_str or path_str.endswith('/integration'):
        return 'integration' not in selected
    if '/e2e/' in path_str or path_str.endswith('/e2e'):
        return 'e2e' not in selected
    return False


def pytest_collection_modifyitems(config, items):
    if not (config.getoption('-m') and 'e2e' in config.getoption('-m')):
        skip_e2e = pytest.mark.skip(reason='need -m e2e to run')
        for item in items:
            if 'e2e' in item.keywords:
                item.add_marker(skip_e2e)

    if not (config.getoption('-m') and 'integration' in config.getoption('-m')):
        skip_integration = pytest.mark.skip(reason='need -m integration to run')
        for item in items:
            if 'integration' in item.keywords:
                item.add_marker(skip_integration)


# Gate external SaaS-dependent tests by env vars


def pytest_runtest_setup(item: pytest.Item):
    def _missing(vars_: list[str]) -> list[str]:
        return [v for v in vars_ if not os.environ.get(v)]

    if item.get_closest_marker('needs_aws'):
        missing = _missing(['AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY', 'AWS_S3_BUCKET'])
        if missing:
            pytest.skip(f'skipped: missing env vars for AWS/S3: {", ".join(missing)}')

    if item.get_closest_marker('needs_openai'):
        missing = _missing(['OPENAI_API_KEY'])
        if missing:
            pytest.skip(f'skipped: missing env vars for OpenAI: {", ".join(missing)}')


# Global defaults and FastAPI auth overrides


@pytest.fixture(scope='session', autouse=True)
def _set_default_env() -> None:
    for key, value in DEFAULT_ENV_VARS.items():
        os.environ.setdefault(key, value)
