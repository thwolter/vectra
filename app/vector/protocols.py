from typing import List

from langchain_core.documents import Document

from app.utils.types import SHA256B64
from app.vector.schemas import IngestionResult


class IngestorProtocol:
    async def ingest(
        self,
        *,
        docs: List[Document],
        digest: SHA256B64,
    ) -> IngestionResult: ...
