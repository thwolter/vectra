from __future__ import annotations

from dataclasses import replace as dc_replace

from langchain_core.documents import Document
from loguru import logger
from sqlmodel.ext.asyncio.session import AsyncSession

from app.metadata.base import Strategy
from app.parsers.protocols import ParserProtocol
from app.repositories import DocumentRepository as DBDocument
from app.repositories import EmbeddingsRepository, IngestionRepository, JobRepository
from app.repositories.schemas import DocumentUpdate, IngestionVersion, JobUpdate
from app.schemas.jobs import JobCtx
from app.services.document_service import DocumentService
from app.store.protocols import StoreProtocol
from app.store.schemas import ArtifactInfo
from app.vector.protocols import IngestorProtocol


class UploadPipeline:
    _ctx: JobCtx | None = None

    def __init__(
        self,
        *,
        store: StoreProtocol,
        parser: ParserProtocol,
        ingestor: IngestorProtocol,
    ) -> None:
        self.store = store
        self.parser = parser
        self.ingestor = ingestor

    def init(self, ctx: JobCtx) -> UploadPipeline:
        """Initialize the pipeline with a new ctx."""
        self._ctx = ctx
        return self

    @property
    def ctx(self) -> JobCtx:
        if not self._ctx:
            raise ValueError('Pipeline has not been initialized yet.')
        return self._ctx

    @ctx.setter
    def ctx(self, value: JobCtx) -> None:
        self._ctx = value

    async def store_original(self) -> UploadPipeline:
        """Store original file in S3 and return ctx with original_key set."""

        # todo: should we add a base path here?
        saved: ArtifactInfo = await self.store.save_original(
            file=self.ctx.file,
            document_id=self.ctx.document_id,
        )
        self.ctx = dc_replace(self.ctx, original_key=(saved.original_key or ''))
        return self

    async def parse_document(self) -> UploadPipeline:
        """Parse document to LangChain Documents using provided parser.

        Ensures each parsed Document has required metadata fields:
        - source: S3 original key (used for repository checks and deletes)
        - digest: deterministic document id used for idempotency and grouping
        """
        result = await self.parser.parse(file=str(self.ctx.file.path))
        markdown = await self.parser.to_markdown()
        docs = list(result.documents or [])
        if docs:
            # Attach required metadata for downstream vector and tests
            for d in docs:
                meta = d.metadata if isinstance(d.metadata, dict) else {}
                if self.ctx.original_key:
                    meta['source'] = self.ctx.file.filename
                meta['digest'] = self.ctx.digest
                d.metadata = meta
        self.ctx = dc_replace(self.ctx, docs=docs, markdown_text=markdown)
        return self

    async def ingest_documents(self, session: AsyncSession) -> UploadPipeline:
        """Ingest documents into vector store with idempotency check.

        Computes a stable content fingerprint based on parsed docs and checks the
        ingestion version repository. If present, skips embedding; otherwise ingests.
        """

        fp = IngestionVersion.from_settings(collection=self.ctx.collection.value).fingerprint()

        ingestion_exists = await IngestionRepository.exists(
            session, fingerprint=fp, collection=self.ctx.collection.value, digest=self.ctx.digest
        )
        if ingestion_exists:
            logger.info(f'{self.ctx.job_id} IngestionVersion exists; skipping chunk/embed')
            self.ctx = dc_replace(self.ctx, skip_embed=True)
            return self

        if self.ctx.docs:
            result = await self.ingestor.ingest(session=session, docs=self.ctx.docs, job_id=self.ctx.job_id)
            await JobRepository.update(session, job=JobUpdate(id=self.ctx.job_id, ingestion_id=result.ingestion_id))

        self.ctx = dc_replace(self.ctx, skip_embed=False)
        return self

    async def store_markdown(self) -> UploadPipeline:
        """Store markdown copy of parsed content.

        If markdown_text is present, save via store.save_markdown and return the same ctx.
        Tests do not require updating markdown_key here; exceptions must propagate.
        """

        if not self.ctx.markdown_text:
            logger.warning('No markdown text to store; skipping.')
            return self
        # Let any exception from the store propagate to the caller
        saved = await self.store.save_markdown(
            self.ctx.markdown_text,
            document_id=self.ctx.document_id,
        )
        # Return the original immutable ctx instance (no replacement)
        self.ctx = dc_replace(self.ctx, markdown_key=(saved.markdown_key or ''))
        return self

    async def enrich_docs_metadata(self) -> UploadPipeline:
        """Ensure required document-level metadata keys are set on each parsed Document.

        Attaches strategy-proposed metadata (as a plain dict) onto each Document.metadata
        and records the ProposedMetadata object on the context for later review.
        """
        if not self.ctx.docs:
            return self

        # Resolve strategy using the full hints object
        strategy = Strategy.from_hints(self.ctx.hints)
        pm = strategy.proposed_metadata()

        # Apply the proposed metadata dict onto each document
        docs: list[Document] = []
        for d in self.ctx.docs:
            d.metadata.update(pm.metadata)
            docs.append(d)

        # Merge proposed metadata into the context metadata without mutating in-place
        base_meta: dict = dict(self.ctx.metadata) if self.ctx.metadata else {}
        if pm.metadata:
            base_meta.update(pm.metadata)
        metadata = base_meta

        # Do not persist here; persistence happens in persist_metadata step
        self.ctx = dc_replace(
            self.ctx,
            docs=docs,
            metadata=metadata,
            needs_review=pm.conflicts != [],
            proposed_metadata=pm,
        )
        return self

    async def persist_metadata(self, session: AsyncSession, update_embeddings: bool = True) -> UploadPipeline:
        """Ensure required metadata keys are set on the DocumentMetadata.

        Uses MetadataService.required_fields to determine which keys are required for the
        current collection, and only attaches those keys when values are available.
        """
        if not self.ctx.metadata:
            return self

        if update_embeddings:
            await EmbeddingsRepository.update_metadata(
                session,
                digest=self.ctx.digest,
                collection=self.ctx.collection.value,
                metadata=self.ctx.metadata,
            )
        await DBDocument.update(
            session,
            document=DocumentUpdate(
                id=self.ctx.document_id,
                meta=self.ctx.metadata,
            ),
        )
        return self

    async def update_document_uris(self, session: AsyncSession) -> UploadPipeline:
        """Update URI fields on the canonical Document via service.

        The service converts store keys to fully-qualified URIs using the collection's
        DocumentStore implementation and persists them via the repository.
        Errors are logged and swallowed to avoid failing the entire job at this stage.
        """
        document_service = DocumentService(collection=self.ctx.collection)
        try:
            await document_service.update_document_uris(
                session=session,
                document_id=self.ctx.document_id,
                original_key=self.ctx.original_key,
                markdown_key=self.ctx.markdown_key,
            )
        except Exception as e:
            raise Exception(f'Failed to update document URIs: {e}')
        return self
