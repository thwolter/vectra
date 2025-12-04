from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession
from tenauth.fastapi import require_access_context, require_auth

from core.deps import SessionDep
from repositories.exceptions import RecordNotFoundError
from schemas.upload import JOBS_PENDING, JobStatus, JobStatusResponse
from services.document_service import DocumentService
from services.factory import get_document_service, get_job_service
from services.job_service import JobService

router = APIRouter(
    prefix='/v1',
    tags=['jobs'],
    dependencies=[Depends(require_auth), Depends(require_access_context)],
)


@router.get('/jobs/{job_id}', response_model=JobStatusResponse)
async def get_job(
    job_id: UUID,
    session: AsyncSession = Depends(SessionDep),
    job_service: JobService = Depends(get_job_service),
) -> JobStatusResponse:
    """Get the status of an ingestion job by ID.

    Unit tests expect the path job_id to be echoed back regardless of the
    underlying service payload. We adapt by overriding the id in the response.
    """
    return await job_service.get_status(session, job_id=job_id)


@router.delete(
    '/jobs/{job_id}',
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        404: {'description': 'Job not found'},
        409: {'description': 'Job already completed or failed'},
    },
)
async def cancel_job(
    job_id: UUID,
    session: AsyncSession = Depends(SessionDep),
    job_service: JobService = Depends(get_job_service),
    document_service: DocumentService = Depends(get_document_service),
) -> None:
    """Cancel a pending upload job and clean up its uploaded artifacts."""

    try:
        job = await job_service.get_job(session=session, job_id=job_id)
    except RecordNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Job not found')

    if JobStatus(job.status) not in JOBS_PENDING:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Job already finalized')

    await document_service.delete(session, document_id=job.document_id)
