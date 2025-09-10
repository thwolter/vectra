import os
import pickle
import sys
import tempfile
from pathlib import Path
from typing import List, Any, Generator, TYPE_CHECKING

import pytest
from fastapi import UploadFile
from langchain_core.documents import Document
from starlette.datastructures import Headers

if TYPE_CHECKING:
    from app.utils.types import SHA256B64

# Ensure project app/ is on sys.path for `from app...` imports in tests
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_SRC_PATH = _PROJECT_ROOT / 'app'
for p in (str(_PROJECT_ROOT), str(_SRC_PATH)):
    if p not in sys.path:
        sys.path.insert(0, p)


def pytest_runtest_setup(item):
    # Expand shorthand markers into requires_env
    if any(item.iter_markers(name='needs_postgres')):
        item.add_marker(pytest.mark.requires_env('POSTGRES_URL'))

    if any(item.iter_markers(name='needs_aws')):
        item.add_marker(
            pytest.mark.requires_env(
                'AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY', 'AWS_S3_BUCKET'
            )
        )

    if any(item.iter_markers(name='needs_openai')):
        item.add_marker(pytest.mark.requires_env('OPENAI_API_KEY'))

    # Generic requires_env marker
    for mark in item.iter_markers(name='requires_env'):
        required = list(mark.args)
        missing = [v for v in required if not os.getenv(v)]
        if missing:
            pytest.skip(f'Missing required env vars: {", ".join(missing)}')


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


@pytest.fixture
def apple_report_first_page():
    return Path(__file__).parents[0] / 'data' / '10-Q4-2024-As-Filed Seite 1.pdf'


@pytest.fixture
def tiny_pdf():
    """Path to a small test PDF located under tests/data."""
    return str(Path(__file__).parents[0] / 'data' / 'tiny.pdf')


@pytest.fixture
def small_pdf():
    """Path to a small test PDF located under tests/data."""
    return str(Path(__file__).parents[0] / 'data' / 'small.pdf')


@pytest.fixture(scope='module')
def tiny_pdf_upload() -> Generator[UploadFile, Any, None]:
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')

    def create_file(content: bytes, tmp):
        tmp.write(content)
        tmp.flush()
        tmp.close()
        f = open(tmp.name, 'rb')
        headers = Headers({'content-type': 'application/pdf'})
        return UploadFile(filename='tiny.pdf', file=f, headers=headers)

    content = b'%PDF-1.4\n%\xe2\xe3\xcf\xd3\n1 0 obj\n<<>>\nendobj\n%%EOF\n'

    try:
        upload = create_file(content, tmp)
        yield upload
    finally:
        try:
            tmp.close()
            os.unlink(tmp.name)
        except FileNotFoundError:
            pass


@pytest.fixture
def digest_str() -> 'SHA256B64':
    return '47DEQpj8HBSa+/TImW+5JCeuQeRkm5NMpJWZG3hSuFU='


@pytest.fixture
def another_digest_str() -> 'SHA256B64':
    return '50DEQpj8HBSa+/TImW+5JCeuQeRkm5NMpJWZG3hSuFU='


@pytest.fixture
def apple_report_first_page_upload(
    apple_report_first_page,
) -> Generator[UploadFile, Any, None]:
    """Create an UploadFile from the apple_report_first_page test PDF.

    Ensures correct content-type header and proper file handle cleanup.
    """
    f = open(apple_report_first_page, 'rb')
    try:
        headers = Headers({'content-type': 'application/pdf'})
        upload = UploadFile(
            filename=Path(apple_report_first_page).name, file=f, headers=headers
        )
        yield upload
    finally:
        try:
            f.close()
        except Exception:
            pass
