from typing import List
from uuid import UUID

from langchain_core.documents import Document
from sqlmodel.ext.asyncio.session import AsyncSession

from app.repositories.schemas import IngestionResult


class IngestorProtocol:
    async def ingest(
        self,
        session: AsyncSession,
        *,
        docs: List[Document],
        job_id: UUID,
    ) -> IngestionResult: ...
