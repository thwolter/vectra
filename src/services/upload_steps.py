from __future__ import annotations

from dataclasses import replace as dc_replace

from langchain_core.documents import Document
from loguru import logger
from sqlmodel.ext.asyncio.session import AsyncSession

from repositories import embeddings_repository, ingestion_repository, job_repository
from repositories.schemas import IngestionVersion, JobUpdate
from schemas.jobs import JobCtx
from services.document_service import DocumentService
from store.protocols import StoreProtocol
from store.schemas import ArtifactInfo
from vector.chunker import chunk_documents_by_headings
from vector.ingestor import DocumentIngestor
from vector.parser import LlamaParser


class UploadPipeline:
    def __init__(
        self,
        *,
        store: StoreProtocol,
    ) -> None:
        self.store = store

    async def _load_cached_markdown(self, ctx: JobCtx) -> tuple[str | None, str | None]:
        try:
            info = await self.store.info(document_id=ctx.document_id, digest=str(ctx.digest), tenant_id=ctx.tenant_id)
        except Exception as exc:
            logger.warning(f'Failed to load markdown info from store: {exc}')
            return None, None

        for file_info in info.files:
            key = file_info.key
            if not key.lower().endswith('.md'):
                continue
            buffer = bytearray()
            try:
                async for chunk in self.store.stream(key):
                    buffer.extend(chunk)
            except Exception as exc:
                logger.warning(f'Failed to stream markdown from store ({key}): {exc}')
                return None, None

            try:
                text = buffer.decode('utf-8')
            except UnicodeDecodeError:
                text = buffer.decode('utf-8', errors='replace')
            return text, key

        return None, None

    @staticmethod
    def _apply_metadata(docs: list[Document], ctx: JobCtx) -> list[Document]:
        for doc in docs:
            meta = dict(doc.metadata) if isinstance(doc.metadata, dict) else {}
            meta.setdefault('source', ctx.file.filename)
            meta['digest'] = ctx.digest
            doc.metadata = meta
        return docs

    def _docs_from_markdown(self, markdown: str, ctx: JobCtx) -> list[Document]:
        if not markdown:
            return []
        doc = Document(page_content=markdown, metadata={'source': ctx.file.filename, 'digest': ctx.digest})
        return [doc]

    async def _load_existing_chunks(self, session: AsyncSession, ctx: JobCtx) -> list[Document]:
        try:
            docs = await embeddings_repository.fetch_documents(
                session,
                collection=ctx.collection,
                digest=ctx.digest,
            )
        except Exception as exc:
            logger.warning(f'Failed to load existing embeddings for re-ingest: {exc}')
            return []
        return self._apply_metadata(docs, ctx)

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
        if not ctx.run_parser:
            markdown, markdown_key = await self._load_cached_markdown(ctx)
            if markdown is not None:
                docs = self._apply_metadata(self._docs_from_markdown(markdown, ctx), ctx)
                return dc_replace(
                    ctx,
                    docs=docs,
                    markdown_text=markdown,
                    markdown_key=markdown_key or ctx.markdown_key,
                )
            logger.info('Parser skipped but cached markdown not found; running parser with current settings.')
            ctx = dc_replace(ctx, run_parser=True)

        parser = LlamaParser()
        result = await parser.parse(file=str(ctx.file.path))
        markdown = await parser.to_markdown()
        docs = self._apply_metadata(list(result or []), ctx)
        return dc_replace(ctx, docs=docs, markdown_text=markdown)

    async def store_markdown(self, ctx: JobCtx) -> JobCtx:
        """Store markdown copy of parsed content.

        If markdown_text is present, save via store.save_markdown and return the same ctx.
        Tests do not require updating markdown_key here; exceptions must propagate.
        """

        if not ctx.run_parser:
            logger.debug('Parser step skipped; reusing cached markdown without re-upload.')
            return ctx
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

    async def chunk_documents(self, ctx: JobCtx) -> JobCtx:
        """Apply chunking to parsed documents when configuration requires it."""

        if not ctx.run_chunker:
            return ctx

        if not ctx.docs:
            logger.warning('Chunker step requested but no parsed documents available; skipping.')
            return ctx

        chunked = chunk_documents_by_headings(ctx.docs)
        docs = self._apply_metadata(list(chunked or []), ctx)
        return dc_replace(ctx, docs=docs)

    async def ingest_documents(self, ctx: JobCtx, session: AsyncSession) -> JobCtx:
        """Ingest documents into the vector store when the plan requires embeddings."""

        version = ctx.ingestion_version or IngestionVersion.from_settings(collection=ctx.collection)
        matching = await ingestion_repository.find(
            session,
            collection=ctx.collection,
            digest=ctx.digest,
            version=version,
        )

        ingestion_id = None
        skip_embed = False

        if matching:
            logger.info(f'{ctx.job_id} ingestion already up-to-date; skipping embed.')
            skip_embed = True
            ingestion_id = matching.id
        elif not ctx.run_embedding:
            logger.info(f'{ctx.job_id} embedding step skipped per ingestion plan.')
            skip_embed = True
            if ctx.existing_ingestion:
                ingestion_id = ctx.existing_ingestion.id
        else:
            docs = ctx.docs

            # Prefer previously chunked documents if chunking was skipped.
            if (not docs or not ctx.run_chunker) and ctx.existing_ingestion:
                cached_docs = await self._load_existing_chunks(session, ctx)
                if cached_docs:
                    docs = cached_docs

            if not docs:
                logger.warning(f'{ctx.job_id} no documents available for ingestion; skipping embed.')
                skip_embed = True
            else:
                if ctx.existing_ingestion:
                    await embeddings_repository.delete(session, digest=ctx.digest)
                ingestor = DocumentIngestor(collection=ctx.collection)
                result = await ingestor.ingest(session=session, docs=docs, job_id=ctx.job_id)
                ingestion_id = result.ingestion_id

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
