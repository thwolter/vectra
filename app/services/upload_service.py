from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.metadata.base import Strategy
from app.parsers.protocols import ParserProtocol
from app.schemas.enums import CollectionEnum
from app.schemas.upload import (
    UploadInitResponse,
    JobStatus,
    StartUploadInput,
    ContinueProcessingInput,
)
from app.services.job_service import JobService
from app.services.upload_steps import UploadPipeline
from app.store.protocols import StoreProtocol

from app.utils.job import build_job_ctx
from loguru import logger

from app.services.document_service import DocumentService
from app.schemas.jobs import InitJob
from app.vector.protocols import IngestorProtocol
from app.protocols.services import UploadServiceProtocol
from app.repositories.ingestion_repository import Ingestion


class UploadService(UploadServiceProtocol):
    """Ingestion service orchestrating upload → parse → store → embed.

    Responsibilities:
    - Compute binary_hash BEFORE any storage to support idempotency.
    - Store original file and markdown copy in S3 using S3DocumentStore.
    - Parse file to documents (DoclingParser) and set source to the S3 original key.
    - Embed/chunk via DocumentIngestor into pgvector with deterministic IDs.
    - Maintain minimal in-memory job status to satisfy the API contract.

    Refactored to small, single-purpose async methods for clarity and testability.
    """

    def __init__(
        self,
        *,
        collection: CollectionEnum = CollectionEnum.DEFAULT,
        parser: ParserProtocol | None = None,
        store: StoreProtocol | None = None,
        ingestor: IngestorProtocol | None = None,
    ) -> None:
        self.collection = collection
        self.parser_provider = parser
        self.pipeline = UploadPipeline(store=store, ingestor=ingestor, parser=parser)
        self.job_service = JobService()

    async def start_document_upload(
        self, session: AsyncSession, *, payload: StartUploadInput
    ) -> UploadInitResponse:
        """Initialize a job and immediately return UploadInitResponse.

        Heavy processing continues asynchronously in the background.
        """

        # Compute stable hash from the uploaded file (streamed)
        digest = await payload.file.sha256_b64()

        document_service = DocumentService(collection=self.collection)
        document_uuid = await document_service.ensure_canonical_document(
            session,
            digest=digest,
            original_filename=payload.file.filename,
            content_type=payload.file.content_type,
            size_bytes=payload.file.size,
        )

        strategy: Strategy = Strategy.from_hints(payload.hints)
        propose_metadata = strategy.proposed_metadata()

        init_job = InitJob(
            document_uuid=document_uuid,
            collection=self.collection.value,
            digest=digest,
            original_filename=payload.file.filename,
            content_type=payload.file.content_type,
            size_bytes=payload.file.size,
            proposed_metadata=propose_metadata,
        )

        job_id = await self.job_service.init_job(session, job=init_job)

        # Early dedup signal based on any existing ingestion version for (collection, digest)
        dedup = await Ingestion.exists_by_digest(
            session,
            digest=digest,
            collection=self.collection.value,
        )

        return UploadInitResponse(
            job_id=job_id,
            document_id=document_uuid,
            status=JobStatus.PROCESSING,  # init call returns processing per API; job status endpoint shows completed
            deduplicated=dedup,
            digest=digest,
            original_filename=payload.file.filename,
        )

    async def continue_processing(
        self,
        session: AsyncSession,
        *,
        payload: ContinueProcessingInput,
    ) -> None:
        """Perform the heavy processing steps for an initialized job.

        This uses precomputed identifiers from the initialization step
        and is intended to be scheduled via FastAPI BackgroundTasks.
        """

        init_ctx = build_job_ctx(payload=payload, collection=self.collection)
        pipeline = self.pipeline.init(init_ctx)
        job_id = init_ctx.job_id

        try:
            await self.job_service.update_progress(
                session, job_id=job_id, percent=10, step='store_original'
            )
            await pipeline.store_original()

            await self.job_service.update_progress(
                session, job_id=job_id, percent=20, step='parse'
            )
            await pipeline.parse_document()

            await self.job_service.update_progress(
                session, job_id=job_id, percent=50, step='store_markdown'
            )
            await pipeline.store_markdown()

            await self.job_service.update_progress(
                session, job_id=job_id, percent=60, step='prepare_metadata'
            )
            await pipeline.enrich_docs_metadata()

            await self.job_service.update_progress(
                session, job_id=job_id, percent=70, step='ingest'
            )
            await pipeline.ingest_documents(session=session)

            await self.job_service.update_progress(
                session, job_id=job_id, percent=90, step='ensure_metadata'
            )
            await pipeline.persist_metadata(session=session)

            await self.job_service.update_progress(
                session, job_id=job_id, percent=95, step='update_s3_uris'
            )
            await pipeline.update_document_uris(session=session)

            job_status = (
                JobStatus.NEEDS_REVIEW
                if pipeline.ctx.needs_review
                else JobStatus.COMPLETED
            )
            await self.job_service.update_status(
                session,
                job_id=job_id,
                status=job_status,
                proposed_metadata=pipeline.ctx.proposed_metadata,
            )
            logger.success(f'Finalized job {job_id}')

        except Exception as e:
            logger.exception(
                f'Background processing failed for job {payload.job_id}: {e}'
            )
            await self.job_service.fail_job(session, job_id=payload.job_id, exc=e)
