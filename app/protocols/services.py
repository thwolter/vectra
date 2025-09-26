from typing import Protocol
from uuid import UUID

from sqlmodel.ext.asyncio.session import AsyncSession

from app.schemas.upload import (
    ContinueProcessingInput,
    JobReviewPayload,
    JobReviewResponse,
    JobStatusResponse,
    StartUploadInput,
    UploadInitResponse,
)


class UploadServiceProtocol(Protocol):
    async def initiate_document_intake(
        self, session: AsyncSession, *, payload: StartUploadInput
    ) -> UploadInitResponse: ...

    async def continue_processing(self, payload: ContinueProcessingInput) -> None: ...


class JobServiceProtocol(Protocol):
    async def get_status(self, status: AsyncSession, *, job_id: UUID) -> JobStatusResponse: ...

    async def review_job(
        self, status: AsyncSession, *, job_id: UUID, payload: JobReviewPayload
    ) -> JobReviewResponse: ...
