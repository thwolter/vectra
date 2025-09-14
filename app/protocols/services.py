from typing import Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.upload import (
    UploadInitResponse,
    StartUploadInput,
    ContinueProcessingInput,
    JobStatusResponse,
    JobReviewPayload,
    JobReviewResponse,
)


class UploadServiceProtocol(Protocol):
    async def start_document_upload(
        self, session: AsyncSession, *, payload: StartUploadInput
    ) -> UploadInitResponse: ...

    async def continue_processing(self, payload: ContinueProcessingInput) -> None: ...


class JobServiceProtocol(Protocol):
    async def get_status(
        self, status: AsyncSession, *, job_id: UUID
    ) -> JobStatusResponse: ...

    async def review_job(
        self, status: AsyncSession, *, job_id: UUID, payload: JobReviewPayload
    ) -> JobReviewResponse: ...
