import pytest

from app.services.factory import get_document_service


@pytest.fixture
def document_service():
    """Create a DocumentService instance for testing."""
    return get_document_service()


@pytest.fixture
def pdf_file_path():
    return 'tests/data/10-Q4-2024-As-Filed Seite 1.pdf'
