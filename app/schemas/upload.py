from __future__ import annotations

import enum
from typing import List, Annotated, Union
from uuid import UUID

from pydantic import BaseModel, Field

from app.api.schemas import AccessContext
from app.api.file import TemporaryUploadFile
from app.metadata.schemas import NoopHints, FinanceReportHints, ProposedMetadata
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
    hints: UploadHints | None = Field(
        default=None, description='Optional routing/parsing hints'
    )


class ContinueProcessingInput(StartUploadInput):
    """Input for continuing background processing.

    Inherits file context and hints from StartUploadInput and adds identifiers
    established during the initialization step to make the dependency explicit.
    """

    job_id: UUID = Field(..., description='Server-generated job identifier (UUID)')
    document_id: UUID = Field(..., description='Stable hex digest for the document')
    digest: SHA256B64 = Field(..., description='SHA-256 hex digest of the document')
    access_context: AccessContext


class JobStatus(enum.Enum):
    QUEUED = 'queued'
    PROCESSING = 'processing'
    NEEDS_REVIEW = 'needs_review'
    COMPLETED = 'completed'
    FAILED = 'failed'


class UploadInitResponse(BaseModel):
    job_id: UUID
    document_id: UUID
    status: JobStatus
    deduplicated: bool = Field(False)
    digest: SHA256B64
    original_filename: str | None = Field(default=None)


class JobProgress(BaseModel):
    percent: Annotated[int, Field(default=0, strict=True, ge=0, le=100)]
    step: str | None = Field(
        None, description='store|parse|extract-meta|validate|chunk|embed|finalize'
    )


class JobStatusResponse(BaseModel):
    job_id: UUID = Field(...)
    status: JobStatus = Field(...)
    progress: JobProgress = Field(
        default_factory=lambda: JobProgress(percent=0, step=None)
    )
    proposed_metadata: ProposedMetadata | None = None
    warnings: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    original_filename: str | None = Field(default=None)


class JobReviewPayload(BaseModel):
    confirm: bool = Field(..., description='True if user confirms proposed metadata')
    corrections: dict | None = Field(
        default=None,
        description='Optional field-level corrections to apply before confirmation',
    )


class JobReviewResponse(BaseModel):
    job_id: UUID = Field(...)
    status: JobStatus = Field(...)
