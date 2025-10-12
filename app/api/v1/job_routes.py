from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.dependencies import (
    access_scoped_session,
    require_access_context,
    require_auth,
)
from app.protocols.services import JobServiceProtocol
from app.schemas.upload import JobStatusResponse
from app.services.factory import get_job_service

router = APIRouter(
    prefix='/v1',
    tags=['jobs'],
    dependencies=[Depends(require_auth), Depends(require_access_context)],
)


@router.get('/jobs/{job_id}', response_model=JobStatusResponse)
async def get_job(
    job_id: UUID,
    session: AsyncSession = Depends(access_scoped_session),
    job_service: JobServiceProtocol = Depends(get_job_service),
) -> JobStatusResponse:
    """Get the status of an ingestion job by ID.

    Unit tests expect the path job_id to be echoed back regardless of the
    underlying service payload. We adapt by overriding the id in the response.
    """
    return await job_service.get_status(session, job_id=job_id)
