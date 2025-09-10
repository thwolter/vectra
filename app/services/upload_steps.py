from __future__ import annotations

from dataclasses import replace as dc_replace

from langchain_core.documents import Document
from loguru import logger

from app.metadata.base import Strategy
from app.parsers.protocols import ParserProtocol
from app.schemas.jobs import JobCtx
from app.vector.protocols import IngestorProtocol
from app.vector.providers import default_ingestor_provider
from app.store.providers import default_store_provider
from app.parsers.providers import parser_provider

from app.repositories.factory import get_ingestion_repository, get_document_repository

from app.services.document_service import DocumentService

from app.repositories.factory import get_embedding_repository
from app.vector.schemas import IngestionVersionKey
from app.store.protocols import StoreProtocol
from app.store.schemas import ArtifactInfo
from app.vector.models import IngestorSettings


class UploadPipeline:
    _ctx: JobCtx | None = None

    def __init__(
        self,
        *,
        store: StoreProtocol | None = None,
        parser: ParserProtocol | None = None,
        ingestor: IngestorProtocol | None = None,
    ) -> None:
        self.store = store
        self.parser = parser
        self.ingestor = ingestor
        self.repo = get_ingestion_repository()

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
        store = self.store or default_store_provider(self.ctx.collection)
        saved: ArtifactInfo = await store.save_original(
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
        parser = self.parser or parser_provider(
            file_path=str(self.ctx.file.path),
            profile='auto',
        )
        result = await parser.parse()
        markdown = await parser.to_markdown()
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

    async def ingest_documents(self) -> UploadPipeline:
        """Ingest documents into vector store with idempotency check.

        Computes a stable content fingerprint based on parsed docs and checks the
        ingestion version repository. If present, skips embedding; otherwise ingests.
        """

        settings = IngestorSettings()
        key = IngestionVersionKey(
            collection=self.ctx.collection.value,
            digest=self.ctx.digest,
            chunker_version=settings.chunker_version,
            embed_model=settings.model_name,
            embed_model_ver=settings.embed_model_ver,
        )

        try:
            exists = await self.repo.exists_by_key(key)
        except Exception as e:
            logger.error(
                f'Failed to check ingestion version for {self.ctx.job_id}: {e}'
            )
            # If check fails, assume it does not exist to avoid skipping ingestion
            exists = False

        if exists:
            logger.info(
                f'{self.ctx.job_id} IngestionVersion exists; skipping chunk/embed'
            )
            self.ctx = dc_replace(self.ctx, skip_embed=True)
            return self

        if self.ctx.docs:
            ingestor = self.ingestor or default_ingestor_provider(
                collection=self.ctx.collection,
            )
            await ingestor.ingest(
                docs=self.ctx.docs,
                digest=self.ctx.digest,
            )
        self.ctx = dc_replace(self.ctx, skip_embed=False)
        return self

    async def store_markdown(self) -> UploadPipeline:
        """Store markdown copy of parsed content.

        If markdown_text is present, save via store.save_markdown and return the same ctx.
        Tests do not require updating markdown_key here; exceptions must propagate.
        """

        # todo: should we add a base path here?
        store = self.store or default_store_provider(self.ctx.collection)
        if not self.ctx.markdown_text:
            logger.warning('No markdown text to store; skipping.')
            return self
        # Let any exception from the store propagate to the caller
        saved = await store.save_markdown(
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
            d.metadata.update(pm.metadata)  # type: ignore[arg-type]
            docs.append(d)

        metadata = (
            self.ctx.metadata.update(pm.metadata) if self.ctx.metadata else pm.metadata
        )

        if metadata:
            documents = get_document_repository()
            await documents.update_metadata(
                id=self.ctx.document_id,
                metadata=metadata,
            )

        self.ctx = dc_replace(
            self.ctx,
            docs=docs,
            metadata=metadata,
            needs_review=pm.conflicts != [],
            proposed_metadata=pm,
        )
        return self

    async def persist_metadata(self) -> UploadPipeline:
        """Ensure required metadata keys are set on the DocumentMetadata.

        Uses MetadataService.required_fields to determine which keys are required for the
        current collection, and only attaches those keys when values are available.
        """
        embeddings = get_embedding_repository()
        documents = get_document_repository()
        if not self.ctx.metadata:
            return self

        try:
            await embeddings.update_metadata(
                self.ctx.digest,
                collection=self.ctx.collection.value,
                metadata=self.ctx.metadata,
            )
            await documents.update_metadata(
                id=self.ctx.document_id,
                metadata=self.ctx.metadata,
            )
        except Exception as e:
            raise Exception(f'Failed to persist metadata: {e}')

        return self

    async def update_document_uris(self) -> UploadPipeline:
        """Update URI fields on the canonical Document via service.

        The service converts store keys to fully-qualified URIs using the collection's
        DocumentStore implementation and persists them via the repository.
        Errors are logged and swallowed to avoid failing the entire job at this stage.
        """
        document_service = DocumentService(collection=self.ctx.collection)
        try:
            await document_service.update_document_uris(
                document_id=self.ctx.document_id,
                original_key=self.ctx.original_key,
                markdown_key=self.ctx.markdown_key,
            )
        except Exception as e:
            raise Exception(f'Failed to update document URIs: {e}')
        return self
