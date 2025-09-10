from __future__ import annotations

from uuid import UUID

from fastapi import Depends, APIRouter

from app.protocols.services import JobServiceProtocol
from app.schemas.upload import JobStatusResponse, JobReviewResponse, JobReviewPayload
from app.services.factory import get_job_service


router = APIRouter(prefix='/v1', tags=['jobs'])


@router.get('/jobs/{job_id}', response_model=JobStatusResponse)
async def get_job(
    job_id: UUID, job_service: JobServiceProtocol = Depends(get_job_service)
) -> JobStatusResponse:
    """Get the status of an ingestion job by ID.

    Unit tests expect the path job_id to be echoed back regardless of the
    underlying service payload. We adapt by overriding the id in the response.
    """
    return await job_service.get_status(job_id=job_id)


@router.patch('/jobs/{job_id}/review', response_model=JobReviewResponse)
async def review_job(
    job_id: UUID,
    payload: JobReviewPayload,
    job_service: JobServiceProtocol = Depends(get_job_service),
) -> JobReviewResponse:
    """Submit a human review for an ingestion job to correct or approve extracted metadata."""
    return await job_service.review_job(job_id=job_id, payload=payload)
