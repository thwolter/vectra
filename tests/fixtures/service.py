import pytest

from app.schemas.enums import CollectionEnum
from app.services.dependencies import get_upload_pipeline, get_upload_service


@pytest.fixture
def upload_pipeline():
    return get_upload_pipeline(collection=CollectionEnum.DEFAULT)


@pytest.fixture
def upload_service(upload_pipeline):
    return get_upload_service()
