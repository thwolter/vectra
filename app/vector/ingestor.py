from functools import cached_property
from typing import List, Sequence

from langchain_core.documents import Document
from loguru import logger

from app.repositories.factory import get_ingestion_repository, get_embedding_repository
from app.utils.types import SHA256B64
from .errors import EmbeddingsAlreadyExistError
from .protocols import IngestorProtocol
from .schemas import IngestionVersionInsert, IngestionResult

from .batching import BatchBuilder
from .factory import get_vectorstore
from .models import IngestorSettings
from app.schemas.enums import CollectionEnum


class DocumentIngestor(IngestorProtocol):
    """
    Handles document ingestion and processing for vector storage.
    This class focuses on document batching, token estimation, and metadata management.
    """

    def __init__(
        self,
        collection: CollectionEnum,
        *,
        ingest_settings: IngestorSettings | None = None,
        vectorstore=None,
        ingestion_repo=None,
        embedding_repo=None,
    ) -> None:
        """Initialize the ingestor with a collection and optional settings."""
        self.collection: CollectionEnum = collection
        self.ingest_settings: IngestorSettings = ingest_settings or IngestorSettings()
        self.batcher = BatchBuilder(self.ingest_settings)
        self._vectorstore = vectorstore
        self._ingestion_repo = ingestion_repo
        self._embedding_repo = embedding_repo

    @cached_property
    def vectorstore(self):
        return self._vectorstore or get_vectorstore(self.collection.value)

    @cached_property
    def ingestion_repo(self):
        return self._ingestion_repo or get_ingestion_repository()

    @cached_property
    def embedding_repo(self):
        return self._embedding_repo or get_embedding_repository()

    async def ingest(
        self, *, docs: List[Document], digest: SHA256B64
    ) -> IngestionResult:
        """
        Ingests documents in batches into the vector.
        Raises:
            EmbeddingsAlreadyExistError: if embeddings already exist for the given digest.
        Returns:
            IngestionResult: summary of the operation.
        """

        if not docs:
            logger.warning('No documents provided for ingestion; skipping.')
            return IngestionResult(
                digest=digest,
                collection=self.collection.value,
                total_docs=0,
                batches=0,
                skipped=True,
                reason='no_documents',
            )

        embeddings_exist = await self.embeddings_exist(digest=digest)
        if embeddings_exist:
            raise EmbeddingsAlreadyExistError(
                f'Embeddings already exist for digest {digest}.'
            )

        batches = self.batch_documents_by_tokens(docs)

        total_ingested = 0
        for batch in batches:
            self.enrich_metadata(batch, digest=digest, offset=total_ingested)
            self.vectorstore.add_documents(documents=batch)
            total_ingested += len(batch)
            logger.debug(
                f"Added {len(batch)} docs with digest {digest}) to collection '{self.vectorstore.collection_name}'"
            )

        await self.mark_ingestion(digest=digest)

        logger.success(
            f"Ingested {total_ingested} documents into collection '{self.collection.value}'"
        )
        return IngestionResult(
            digest=digest,
            collection=self.collection.value,
            total_docs=total_ingested,
            batches=len(batches),
        )

    @staticmethod
    def enrich_metadata(
        batch: Sequence, *, digest: SHA256B64, offset: int = 0
    ) -> Sequence:
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

    def batch_documents_by_tokens(self, docs: List[Document]) -> List[List[Document]]:
        return self.batcher.batch_documents_by_tokens(docs)

    def plan_batches(self, docs: list[Document]) -> list[list[Document]]:
        return self.batcher.batch_documents_by_tokens(docs)

    async def mark_ingestion(self, digest: SHA256B64) -> None:
        """Persist an ingestion version row for traceability and idempotency."""
        payload = IngestionVersionInsert(
            collection=self.collection.value,
            digest=digest,
            chunker_version=self.ingest_settings.chunker_version,
            embed_model=self.ingest_settings.model_name,
            embed_model_ver=self.ingest_settings.embed_model_ver,
        )
        await self.ingestion_repo.insert_Key(payload)

    async def delete_embeddings(self, *, digest: SHA256B64) -> None:
        """Delete embeddings for a given digest."""
        try:
            await self.embedding_repo.delete(digest=digest)
            await self.ingestion_repo.delete_by_digest(
                digest=digest, collection=self.collection.value
            )
        except Exception as e:
            logger.error(f'Failed to delete embeddings for digest {digest}: {e}')
            raise

    async def embeddings_exist(self, *, digest: SHA256B64) -> bool:
        """Check if embeddings exist for a given digest."""
        return await self.ingestion_repo.exists_by_digest(
            digest=digest, collection=self.collection.value
        )
