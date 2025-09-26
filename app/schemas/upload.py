from __future__ import annotations

import enum
from typing import Annotated, List, Union
from uuid import UUID

from pydantic import BaseModel, Field

from app.api.file import TemporaryUploadFile
from app.api.schemas import AccessContext
from app.metadata.schemas import FinanceReportHints, NoopHints, ProposedMetadata
from app.utils.types import SHA256B64


class Strategy(enum.Enum):
    FINANCE_REPORT = 'finance_report'
    NOOP = 'noop'


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


# todo: we may require this but must be implemented
class UploadConfig(BaseModel):
    source_scope: SourceScope = SourceScope.PRIVATE
    parser_profile: ParserProfile = ParserProfile.AUTO
    embedding_profile: EmbeddingProfile = EmbeddingProfile.DEFAULT
    ingestion_mode: IngestionMode = IngestionMode.STANDARD
    dry_run: bool | None = Field(default=False)
    idempotency_key: str | None = Field(default=None)


# Discriminated union type for validation and adapters
UploadHints = Annotated[
    Union[FinanceReportHints, NoopHints],
    Field(discriminator='strategy'),
]


class StartUploadInput(BaseModel):
    """Input for starting a document upload.

    Fields map 1:1 to UploadJobService.start_document_upload parameters.
    """

    file: TemporaryUploadFile = Field(..., description='File object')
    hints: UploadHints | None = Field(default=None, description='Optional routing/parsing hints')


class ContinueProcessingInput(StartUploadInput):
    """Input for continuing background processing.

    Inherits file context and hints from StartUploadInput and adds identifiers
    established during the initialization step to make the dependency explicit.
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

        if self.hints is not None:
            data['hints'] = self.hints.model_dump()

        access_context = self.access_context.model_dump()
        access_context['tenant_id'] = str(access_context['tenant_id'])
        access_context['user_id'] = str(access_context['user_id'])
        data['access_context'] = access_context
        return data

    @classmethod
    def from_message(cls, data: dict) -> 'ContinueProcessingInput':
        """Rebuild a ContinueProcessingInput instance from a queue message dict."""
        file = TemporaryUploadFile.from_serialized(data['file'])

        hints_data = data.get('hints')
        hints = None
        if hints_data:
            strategy = hints_data.get('strategy')
            if strategy == 'finance_report':
                hints = FinanceReportHints.model_validate(hints_data)
            else:
                hints = NoopHints.model_validate(hints_data)

        access_context_data = data['access_context']
        access_context = AccessContext(
            tenant_id=UUID(access_context_data['tenant_id']),
            user_id=UUID(access_context_data['user_id']),
        )

        return cls(
            file=file,
            hints=hints,
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
    step: str | None = Field(None, description='store|parse|extract-meta|validate|chunk|embed|finalize')


class JobStatusResponse(BaseModel):
    job_id: UUID = Field(...)
    status: JobStatus = Field(...)
    progress: JobProgress = Field(default_factory=lambda: JobProgress(percent=0, step=None))
    proposed_metadata: ProposedMetadata | None = None
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


class JobReviewPayload(BaseModel):
    confirm: bool = Field(..., description='True if user confirms proposed metadata')
    corrections: dict | None = Field(
        default=None,
        description='Optional field-level corrections to apply before confirmation',
    )


class JobReviewResponse(BaseModel):
    job_id: UUID = Field(...)
    status: JobStatus = Field(...)
