from typing import List, Sequence
from uuid import UUID

from langchain_core.documents import Document
from loguru import logger
from sqlmodel.ext.asyncio.session import AsyncSession

from repositories import (
    IngestionRepository,
    JobRepository,
    ingestion_repository,
    job_repository,
)
from repositories.models import JobRecord
from repositories.schemas import IngestionCreate, IngestionResult, IngestionVersion

from .batching import batch_documents_by_tokens
from .errors import EmbeddingsAlreadyExistError
from .factory import get_vectorstore


class DocumentIngestor:
    """
    Handles document ingestion and processing for vector storage.
    Collection is a plain `str`; tenant scoping is enforced by DB RLS.
    This class focuses on document batching, token estimation, and metadata management.
    """

    def __init__(
        self,
        collection: str,
        *,
        ingestion_repo: IngestionRepository | None = None,
        job_repo: JobRepository | None = None,
    ) -> None:
        """Initialize the ingestor with a collection and optional settings."""
        self.collection = collection
        self._ingestion_repo = ingestion_repo or ingestion_repository
        self._job_repo = job_repo or job_repository

    async def ingest(self, session: AsyncSession, *, docs: List[Document], job_id: UUID) -> IngestionResult:
        """
        Ingests documents in batches into the vector.
        Raises:
            EmbeddingsAlreadyExistError: if embeddings already exist for the given digest.
        Returns:
            IngestionResult: summary of the operation.
        """

        job = await self._job_repo.get(session, job_id=job_id)
        digest = job.document.digest
        if not docs:
            logger.warning('No documents provided for ingestion; skipping.')
            return IngestionResult(
                digest=digest,
                collection=self.collection,
                total_docs=0,
                batches=0,
                skipped=True,
                reason='no_documents',
                ingestion_id=None,
            )

        embeddings_exist = await self.embeddings_exist(session=session, digest=digest)
        if embeddings_exist:
            raise EmbeddingsAlreadyExistError(f'Embeddings already exist for digest {digest}.')

        batches = batch_documents_by_tokens(docs)

        vs = get_vectorstore(collection=self.collection, tenant_id=session.info['tenant_id'])

        total_ingested = 0
        for batch in batches:
            self.enrich_metadata(batch, digest=digest, offset=total_ingested)
            await vs.aadd_documents(documents=batch)
            total_ingested += len(batch)
            logger.debug(f"Added {len(batch)} docs with digest {digest}) to collection '{self.collection}'")

        ingestion_id = await self.mark_ingestion(session=session, job=job, digest=digest, num_chunks=total_ingested)

        logger.success(f"Ingested {total_ingested} documents into collection '{self.collection}'")
        return IngestionResult(
            digest=digest,
            collection=self.collection,
            total_docs=total_ingested,
            batches=len(batches),
            ingestion_id=ingestion_id,
        )

    @staticmethod
    def enrich_metadata(batch: Sequence, *, digest: str, offset: int = 0) -> Sequence:
        for idx, doc in enumerate(batch, start=offset):
            if not isinstance(doc.metadata, dict):
                doc.metadata = {}
            doc.metadata.update(
                {
                    'chunk_id': idx,
                    'digest': digest,
                }
            )
        return batch

    async def mark_ingestion(self, session: AsyncSession, *, job: JobRecord, digest: str, num_chunks: int) -> UUID:
        """Persist an ingestion version row for traceability and idempotency."""
        payload = IngestionCreate.create(
            collection=self.collection,
            digest=digest,
            document_id=job.document_id,
            job_id=job.id,
            num_chunks=num_chunks,
        )
        record = await self._ingestion_repo.create(session=session, data=payload)
        return record.id

    async def embeddings_exist(self, session: AsyncSession, *, digest: str) -> bool:
        """Check if embeddings exist for a given digest."""
        version = IngestionVersion.from_settings(collection=self.collection)
        return await self._ingestion_repo.exists(
            session,
            collection=self.collection,
            digest=digest,
            version=version,
        )
