import pytest

from app.schemas.enums import CollectionEnum
from app.services.document_service import DocumentService


@pytest.fixture
def document_service():
    """Create a DocumentService instance for testing."""
    return DocumentService(collection=CollectionEnum.DEFAULT)


@pytest.fixture
def pdf_file_path():
    return 'tests/data/10-Q4-2024-As-Filed Seite 1.pdf'
