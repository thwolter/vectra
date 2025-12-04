from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from repositories import JobRepository
from repositories.exceptions import RecordNotFoundError
from schemas.upload import JobStatus
from services.job_service import JobService


async def test_is_job_active_returns_true_for_pending_status():
    repo = AsyncMock(spec=JobRepository)
    job = SimpleNamespace(status=JobStatus.PROCESSING.value)
    repo.get.return_value = job
    service = JobService(job_repository=repo)

    assert await service.is_job_active(AsyncMock(), job_id=uuid4())


async def test_is_job_active_returns_false_for_finalized_status():
    repo = AsyncMock(spec=JobRepository)
    job = SimpleNamespace(status=JobStatus.COMPLETED.value)
    repo.get.return_value = job
    service = JobService(job_repository=repo)

    assert not await service.is_job_active(AsyncMock(), job_id=uuid4())


@pytest.mark.parametrize('status', [JobStatus.FAILED, JobStatus.DUPLICATED])
async def test_is_job_active_handles_final_statuses(status):
    repo = AsyncMock(spec=JobRepository)
    job = SimpleNamespace(status=status.value)
    repo.get.return_value = job
    service = JobService(job_repository=repo)

    assert not await service.is_job_active(AsyncMock(), job_id=uuid4())


async def test_is_job_active_handles_missing_job():
    repo = AsyncMock(spec=JobRepository)
    repo.get.side_effect = RecordNotFoundError('job missing')
    service = JobService(job_repository=repo)

    assert not await service.is_job_active(AsyncMock(), job_id=uuid4())
