from __future__ import annotations

from dataclasses import replace as dc_replace

from langchain_core.documents import Document
from loguru import logger
from sqlmodel.ext.asyncio.session import AsyncSession

from app.extract.agent import extract_metadata as run_extract_agent
from app.metadata.base import Strategy
from app.metadata.config import ExtractConfig
from app.parsers.protocols import ParserProtocol
from app.repositories import DocumentRepository as DBDocument
from app.repositories import EmbeddingsRepository, IngestionRepository, JobRepository
from app.repositories.schemas import DocumentUpdate, IngestionVersion, JobUpdate
from app.schemas.jobs import JobCtx
from app.services.document_service import DocumentService
from app.store.protocols import StoreProtocol
from app.store.schemas import ArtifactInfo
from app.vector.models import IngestorSettings
from app.vector.protocols import IngestorProtocol


class UploadPipeline:
    def __init__(
        self,
        *,
        store: StoreProtocol,
        parser: ParserProtocol,
        ingestor: IngestorProtocol,
        extract_config: ExtractConfig,
    ) -> None:
        self.store = store
        self.parser = parser
        self.ingestor = ingestor
        self.extract_config = extract_config

    async def store_original(self, ctx: JobCtx) -> JobCtx:
        """Store original file in S3 and return ctx with original_key set."""

        # todo: should we add a base path here?
        saved: ArtifactInfo = await self.store.save_original(
            file=ctx.file,
            document_id=ctx.document_id,
        )
        return dc_replace(ctx, original_key=(saved.original_key or ''))

    async def parse_document(self, ctx: JobCtx) -> JobCtx:
        """Parse document to LangChain Documents using provided parser.

        Ensures each parsed Document has required metadata fields:
        - source: S3 original key (used for repository checks and deletes)
        - digest: deterministic document id used for idempotency and grouping
        """
        result = await self.parser.parse(file=str(ctx.file.path))
        markdown = await self.parser.to_markdown()
        docs = list(result.documents or [])
        if docs:
            # Attach required metadata for downstream vector and tests
            for d in docs:
                meta = d.metadata if isinstance(d.metadata, dict) else {}
                if ctx.original_key:
                    meta['source'] = ctx.file.filename
                meta['digest'] = ctx.digest
                d.metadata = meta
        return dc_replace(ctx, docs=docs, markdown_text=markdown)

    async def store_markdown(self, ctx: JobCtx) -> JobCtx:
        """Store markdown copy of parsed content.

        If markdown_text is present, save via store.save_markdown and return the same ctx.
        Tests do not require updating markdown_key here; exceptions must propagate.
        """

        if not ctx.markdown_text:
            logger.warning('No markdown text to store; skipping.')
            return ctx
        # Let any exception from the store propagate to the caller
        saved = await self.store.save_markdown(
            ctx.markdown_text,
            document_id=ctx.document_id,
        )
        # Return the original immutable ctx instance (no replacement)
        return dc_replace(ctx, markdown_key=(saved.markdown_key or ''))

    async def enrich_docs_metadata(self, ctx: JobCtx) -> JobCtx:
        """Ensure required document-level metadata keys are set on each parsed Document.

        Attaches strategy-proposed metadata (as a plain dict) onto each Document.metadata
        and records the ProposedMetadata object on the context for later review.
        """
        if not ctx.docs:
            return ctx

        # Resolve strategy using the full hints object
        strategy = Strategy.from_hints(ctx.hints)
        pm = strategy.proposed_metadata()

        # Apply the proposed metadata dict onto each document
        docs: list[Document] = []
        for d in ctx.docs:
            d.metadata.update(pm.metadata)
            docs.append(d)

        # Merge proposed metadata into the context metadata without mutating in-place
        base_meta: dict = dict(ctx.metadata) if ctx.metadata else {}
        if pm.metadata:
            base_meta.update(pm.metadata)
        metadata = base_meta

        # Do not persist here; persistence happens in persist_metadata step
        return dc_replace(
            ctx,
            docs=docs,
            metadata=metadata,
            needs_review=pm.conflicts != [],
            proposed_metadata=pm,
        )

    async def ingest_documents(self, ctx: JobCtx, session: AsyncSession) -> JobCtx:
        """Ingest documents into vector store with idempotency check.

        Computes a stable content fingerprint based on parsed docs and checks the
        ingestion version repository. If present, skips embedding; otherwise ingests.
        """

        fp = IngestionVersion.from_settings(collection=ctx.collection).fingerprint()

        record = await IngestionRepository.find(session, fingerprint=fp, collection=ctx.collection, digest=ctx.digest)

        ingestion_id = None
        skip_embed = False
        if record:
            logger.info(f'{ctx.job_id} IngestionVersion exists; skipping chunk/embed')
            skip_embed = True
            ingestion_id = record.id
        elif ctx.docs:
            skip_embed = False
            result = await self.ingestor.ingest(session=session, docs=ctx.docs, job_id=ctx.job_id)
            ingestion_id = result.ingestion_id
        else:
            skip_embed = False

        if ingestion_id:
            await JobRepository.update(session, job=JobUpdate(id=ctx.job_id, ingestion_id=ingestion_id))

        return dc_replace(ctx, skip_embed=skip_embed)

    async def extract_metadata(self, ctx: JobCtx, session: AsyncSession) -> JobCtx:
        """Run the extraction agent and merge results into context and docs.

        Uses vectorstore contents (by digest and collection) to extract document-level
        metadata. Merges the extracted plain metadata fields into ctx.metadata and
        attaches the full ProposedMetadata (with evidence) to ctx.proposed_metadata.
        """
        # Invoke agent with defaults; hints come from ctx
        proposed = await run_extract_agent(
            session,
            digest=ctx.digest,
            collection=ctx.collection,
            hints=ctx.hints,
            ingestor_config=getattr(self.ingestor, 'config', IngestorSettings()),
            extract_config=self.extract_config,
        )

        # Extract the flat metadata dict from the agent response
        md_all = proposed.metadata or {}
        extracted_plain = {}
        if isinstance(md_all, dict):
            extracted_plain = dict(md_all.get('metadata') or {})

        # Merge into existing context metadata and propagate to docs
        base_meta: dict = dict(ctx.metadata or {})
        if extracted_plain:
            base_meta.update(extracted_plain)

        docs: list[Document] = []
        if ctx.docs:
            for d in ctx.docs:
                d.metadata.update(extracted_plain)
                docs.append(d)

        # Heuristic: needs_review if any key is missing/null
        keys = ('company', 'financial_year', 'document_type')
        needs_review = any(extracted_plain.get(k) in (None, '') for k in keys)

        return dc_replace(
            ctx,
            docs=docs or ctx.docs,
            metadata=base_meta,
            proposed_metadata=proposed,
            needs_review=needs_review,
        )

    async def persist_metadata(self, ctx: JobCtx, session: AsyncSession, update_embeddings: bool = True) -> JobCtx:
        """Ensure required metadata keys are set on the DocumentMetadata.

        Uses MetadataService.required_fields to determine which keys are required for the
        current collection, and only attaches those keys when values are available.
        """
        if not ctx.metadata:
            return ctx

        if update_embeddings:
            await EmbeddingsRepository.update_metadata(
                session,
                digest=ctx.digest,
                collection=ctx.collection,
                metadata=ctx.metadata,
            )
        await DBDocument.update(
            session,
            document=DocumentUpdate(
                id=ctx.document_id,
                meta=ctx.metadata,
            ),
        )
        return ctx

    async def update_document_uris(self, ctx: JobCtx, session: AsyncSession) -> JobCtx:
        """Update URI fields on the canonical Document via service.

        The service converts store keys to fully-qualified URIs using the collection's
        DocumentStore implementation and persists them via the repository.
        Errors are logged and swallowed to avoid failing the entire job at this stage.
        """
        document_service = DocumentService()
        try:
            await document_service.update_document_uris(
                session=session,
                document_id=ctx.document_id,
                original_key=ctx.original_key,
                markdown_key=ctx.markdown_key,
            )
        except Exception as e:
            raise Exception(f'Failed to update document URIs: {e}')
        return ctx
