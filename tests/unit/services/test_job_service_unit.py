import uuid
from unittest.mock import create_autospec

import pytest

from app.repositories import JobRepository
from app.services.job_service import JobService


@pytest.fixture(scope='function')
def job_svc():
    fake_repo = create_autospec(JobRepository)
    fake_repo.create.return_value = (uuid.uuid4(), True)
    fake_repo.get.return_value = None
    return JobService(job_repository=fake_repo)
