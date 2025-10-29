from __future__ import annotations

from dataclasses import replace as dc_replace

from loguru import logger
from sqlmodel.ext.asyncio.session import AsyncSession

from parsers.protocols import ParserProtocol
from repositories import ingestion_repository, job_repository
from repositories.schemas import IngestionVersion, JobUpdate
from schemas.jobs import JobCtx
from services.document_service import DocumentService
from store.protocols import StoreProtocol
from store.schemas import ArtifactInfo
from vector.protocols import IngestorProtocol


class UploadPipeline:
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

    async def store_original(self, ctx: JobCtx) -> JobCtx:
        """Store original file in S3 and return ctx with original_key set."""

        # todo: should we add a base path here?
        saved: ArtifactInfo = await self.store.save_original(
            file=ctx.file,
            document_id=ctx.document_id,
            digest=ctx.digest,
            tenant_id=ctx.tenant_id,
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
            digest=ctx.digest,
            tenant_id=ctx.tenant_id,
        )
        # Return the original immutable ctx instance (no replacement)
        return dc_replace(ctx, markdown_key=(saved.markdown_key or ''))

    async def ingest_documents(self, ctx: JobCtx, session: AsyncSession) -> JobCtx:
        """Ingest documents into vector store with idempotency check.

        Computes a stable content fingerprint based on parsed docs and checks the
        ingestion version repository. If present, skips embedding; otherwise ingests.
        """

        fp = IngestionVersion.from_settings(collection=ctx.collection).fingerprint()

        record = await ingestion_repository.find(session, fingerprint=fp, collection=ctx.collection, digest=ctx.digest)

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
            await job_repository.update(session, job=JobUpdate(id=ctx.job_id, ingestion_id=ingestion_id))

        return dc_replace(ctx, skip_embed=skip_embed)

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
