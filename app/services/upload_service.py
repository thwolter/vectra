from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from dataclasses import dataclass
from functools import partial
from typing import Awaitable, Callable, Any

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
from app.repositories import Ingestion
from app.repositories import Job
from app.core.dependencies import (
    get_database_manager,
    access_scoped_session_ctx,
)


@dataclass(frozen=True)
class _Step:
    percent: int
    step: str
    call: Callable[[], Awaitable[Any]]


class UploadService(UploadServiceProtocol):
    """Ingestion service orchestrating upload → parse → store → embed."""

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
        self.db = get_database_manager()

    async def start_document_upload(
        self, session: AsyncSession, *, payload: StartUploadInput
    ) -> UploadInitResponse:
        """Initialize a job and immediately return UploadInitResponse.

        Heavy processing continues asynchronously in the background.
        """

        # Compute stable hash from the uploaded file (streamed)
        digest = await payload.file.sha256_b64()

        document_service = DocumentService(collection=self.collection)
        document_uuid, _ = await document_service.ensure_canonical_document(
            session,
            digest=digest,
            original_filename=payload.file.filename,
            content_type=payload.file.content_type,
            size_bytes=payload.file.size,
        )

        job_record = None
        if job_id := await Job.find(
            session,
            digest=digest,
            collection=self.collection.value,
            document_id=document_uuid,
        ):
            logger.info(f'Found existing job {job_id} for {digest}')
            job_record = await Job.get(session, job_id=job_id)
        else:
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
        dedup = await Ingestion.exists(
            session,
            digest=digest,
            collection=self.collection.value,
        )

        status = JobStatus(job_record.status) if job_record else JobStatus.PROCESSING
        original_filename = (
            job_record.original_filename if job_record else payload.file.filename
        )

        return UploadInitResponse(
            job_id=job_id,
            document_id=document_uuid,
            status=status,
            deduplicated=dedup,
            digest=digest,
            original_filename=original_filename,
        )

    async def continue_processing(
        self,
        payload: ContinueProcessingInput,
    ) -> None:
        """Perform the heavy processing steps for an initialized job.

        This uses precomputed identifiers from the initialization step
        and is intended to be scheduled via FastAPI BackgroundTasks.
        """

        init_ctx = build_job_ctx(payload=payload, collection=self.collection)
        pipeline = self.pipeline.init(init_ctx)
        job_id = init_ctx.job_id

        async with access_scoped_session_ctx(payload.access_context) as session:
            steps: list[_Step] = [
                _Step(10, "store_original", pipeline.store_original),
                _Step(20, "parse", pipeline.parse_document),
                _Step(50, "store_markdown", pipeline.store_markdown),
                _Step(60, "prepare_metadata", pipeline.enrich_docs_metadata),
                _Step(70, "ingest", partial(pipeline.ingest_documents, session=session)),
                _Step(90, "ensure_metadata", partial(pipeline.persist_metadata, session=session)),
                _Step(95, "update_s3_uris", partial(pipeline.update_document_uris, session=session)),
            ]

            for s in steps:
                success = await self._run_step(session, job_id, s)
                if not success:
                    return

            job_status = (
                JobStatus.NEEDS_REVIEW if pipeline.ctx.needs_review else JobStatus.COMPLETED
            )
            await self.job_service.update_status(
                session,
                job_id=job_id,
                status=job_status,
                proposed_metadata=pipeline.ctx.proposed_metadata,
            )
            logger.success(f"Finalized job {job_id}")


    async def _run_step(self, session: AsyncSession, job_id: UUID, step: _Step) -> bool:
        await self.job_service.update_progress(
            session, job_id=job_id, percent=step.percent, step=step.step
        )
        try:
            await step.call()
            return True
        except Exception as e:
            logger.exception(
                f"Background processing failed for job {job_id} ({step.step}): {e}"
            )
            await self.job_service.fail_job(session, job_id=job_id, exc=e, last_step=step.step)
            return False