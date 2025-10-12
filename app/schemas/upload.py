from __future__ import annotations

import enum
from typing import Annotated, List
from uuid import UUID

from pydantic import BaseModel, Field
from tenauth.schemas import AccessContext

from app.api.file import TemporaryUploadFile
from app.utils.types import SHA256B64


class SourceScope(enum.Enum):
    PRIVATE = 'private'
    SHARED = 'shared'


class ParserProfile(enum.Enum):
    AUTO = 'auto'
    LARGE = 'large'


class EmbeddingProfile(enum.Enum):
    DEFAULT = 'default'
    LARGE = 'large'


class IngestionMode(enum.Enum):
    STRICT = 'strict'
    STANDARD = 'standard'
    FAST = 'fast'


class UploadConfig(BaseModel):
    source_scope: SourceScope = SourceScope.PRIVATE
    parser_profile: ParserProfile = ParserProfile.AUTO
    embedding_profile: EmbeddingProfile = EmbeddingProfile.DEFAULT
    ingestion_mode: IngestionMode = IngestionMode.STANDARD
    dry_run: bool | None = Field(default=False)
    idempotency_key: str | None = Field(default=None)


class StartUploadInput(BaseModel):
    """Input for starting a document upload.

    Fields map 1:1 to UploadJobService.start_document_upload parameters.
    """

    file: TemporaryUploadFile = Field(..., description='File object')


class ContinueProcessingInput(StartUploadInput):
    """Input for continuing background processing.

    Inherits file context from StartUploadInput and adds identifiers established
    during the initialization step to make the dependency explicit.
    """

    job_id: UUID = Field(..., description='Server-generated job identifier (UUID)')
    document_id: UUID = Field(..., description='Stable hex digest for the document')
    digest: SHA256B64 = Field(..., description='SHA-256 hex digest of the document')
    access_context: AccessContext

    def to_message(self) -> dict:
        """Serialize this payload for message queue transport.

        Ensures UUIDs and complex fields are converted to plain types.
        """
        data = self.model_dump()
        data['job_id'] = str(self.job_id)
        data['document_id'] = str(self.document_id)
        data['file'] = self.file.to_serializable()

        access_context = self.access_context.model_dump()
        access_context['tenant_id'] = str(access_context['tenant_id'])
        access_context['user_id'] = str(access_context['user_id'])
        data['access_context'] = access_context
        return data

    @classmethod
    def from_message(cls, data: dict) -> 'ContinueProcessingInput':
        """Rebuild a ContinueProcessingInput instance from a queue message dict."""
        file = TemporaryUploadFile.from_serialized(data['file'])

        access_context_data = data['access_context']
        access_context = AccessContext(
            tenant_id=UUID(access_context_data['tenant_id']),
            user_id=UUID(access_context_data['user_id']),
        )

        return cls(
            file=file,
            job_id=UUID(data['job_id']),
            document_id=UUID(data['document_id']),
            digest=data['digest'],
            access_context=access_context,
        )


class JobStatus(enum.Enum):
    QUEUED = 'queued'
    PROCESSING = 'processing'
    NEEDS_REVIEW = 'needs_review'
    COMPLETED = 'completed'
    FAILED = 'failed'


JOBS_PENDING = [JobStatus.QUEUED, JobStatus.PROCESSING]


class UploadInitResponse(BaseModel):
    job_id: UUID
    document_id: UUID
    status: JobStatus
    already_running: bool = Field(False)
    digest: SHA256B64
    original_filename: str | None = Field(default=None)


class JobProgress(BaseModel):
    percent: Annotated[int, Field(default=0, strict=True, ge=0, le=100)]
    step: str | None = Field(None, description='store_original|parse|store_markdown|ingest|update_s3_uris')


class JobStatusResponse(BaseModel):
    job_id: UUID = Field(...)
    status: JobStatus = Field(...)
    progress: JobProgress = Field(default_factory=lambda: JobProgress(percent=0, step=None))
    warnings: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    original_filename: str | None = Field(default=None)

    @classmethod
    def job_not_found(cls, job_id: UUID) -> 'JobStatusResponse':
        return JobStatusResponse(
            job_id=job_id,
            status=JobStatus.FAILED,
            progress=JobProgress(percent=0, step=None),
            errors=['job_not_found'],
        )
