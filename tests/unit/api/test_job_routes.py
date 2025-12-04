from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from api.v1.job_routes import cancel_job
from repositories.exceptions import RecordNotFoundError
from schemas.upload import JobStatus
from services.document_service import DocumentService
from services.job_service import JobService


async def test_cancel_job_deletes_document_for_pending_job():
    job_service = AsyncMock(spec=JobService)
    document_service = AsyncMock(spec=DocumentService)
    session = AsyncMock()
    job_id = uuid4()
    document_id = uuid4()
    job = SimpleNamespace(id=job_id, document_id=document_id, status=JobStatus.PROCESSING.value)
    job_service.get_job.return_value = job

    await cancel_job(job_id, session, job_service, document_service)

    document_service.delete.assert_awaited_once_with(session, document_id=document_id)


async def test_cancel_job_raises_not_found_when_missing_job():
    job_service = AsyncMock(spec=JobService)
    document_service = AsyncMock(spec=DocumentService)
    session = AsyncMock()
    job_service.get_job.side_effect = RecordNotFoundError('job missing')

    with pytest.raises(HTTPException) as exc:
        await cancel_job(uuid4(), session, job_service, document_service)

    assert exc.value.status_code == 404


async def test_cancel_job_rejects_finalized_status():
    job_service = AsyncMock(spec=JobService)
    document_service = AsyncMock(spec=DocumentService)
    session = AsyncMock()
    job = SimpleNamespace(id=uuid4(), document_id=uuid4(), status=JobStatus.COMPLETED.value)
    job_service.get_job.return_value = job

    with pytest.raises(HTTPException) as exc:
        await cancel_job(job.id, session, job_service, document_service)

    assert exc.value.status_code == 409
    document_service.delete.assert_not_awaited()
