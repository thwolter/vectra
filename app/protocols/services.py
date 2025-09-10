from typing import Protocol
from uuid import UUID

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
        self, job_input: StartUploadInput
    ) -> UploadInitResponse: ...

    async def continue_processing(self, job_input: ContinueProcessingInput) -> None: ...


class JobServiceProtocol(Protocol):
    async def get_status(self, *, job_id: UUID) -> JobStatusResponse: ...

    async def review_job(
        self, *, job_id: UUID, payload: JobReviewPayload
    ) -> JobReviewResponse: ...
