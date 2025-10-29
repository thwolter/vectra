import pytest

from services.factory import (
    get_profile_settings,
    get_upload_pipeline,
    get_upload_service,
)
from tests.support.profiles import TestProcessingProfile  # type: ignore[missing-import]


@pytest.fixture
def upload_pipeline():
    profile = get_profile_settings(TestProcessingProfile.name)
    return get_upload_pipeline(profile=profile)


@pytest.fixture
def upload_service(upload_pipeline):
    return get_upload_service(profile_name=TestProcessingProfile.name)
