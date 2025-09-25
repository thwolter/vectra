import pytest

from app.services.factory import (
    get_profile_settings,
    get_upload_pipeline,
    get_upload_service,
)


@pytest.fixture
def upload_pipeline():
    return get_upload_pipeline(profile=get_profile_settings('default'))


@pytest.fixture
def upload_service(upload_pipeline):
    return get_upload_service()
