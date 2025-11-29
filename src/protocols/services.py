from typing import Protocol

from sqlmodel.ext.asyncio.session import AsyncSession

from schemas.upload import ContinueProcessingInput, StartUploadInput, UploadInitResponse


class UploadServiceProtocol(Protocol):
    async def initiate_document_intake(
        self, session: AsyncSession, *, payload: StartUploadInput
    ) -> UploadInitResponse: ...

    async def continue_processing(self, payload: ContinueProcessingInput) -> None: ...
