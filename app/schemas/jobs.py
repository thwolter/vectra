from __future__ import annotations

from dataclasses import dataclass, field
from typing import Annotated
from uuid import UUID

from langchain_core.documents import Document
from pydantic import BaseModel, Field, field_validator

from app.api.file import TemporaryUploadFile
from app.schemas.enums import CollectionEnum
from app.metadata.schemas import ProposedMetadata, NoopHints, FinanceReportHints
from app.schemas.upload import JobStatus
from app.utils.types import SHA256B64


class InitJob(BaseModel):
    """Schema used by JobService.init_job to initialize a job.

    This represents the canonical inputs coming from the upload pipeline before
    the job row is created in the database.
    """

    job_id: UUID
    document_uuid: UUID
    collection: str
    digest: SHA256B64
    original_filename: str | None = None
    content_type: str | None = None
    size_bytes: int | None = None
    proposed_metadata: ProposedMetadata | None = None

    @classmethod
    def model_validate(cls, obj):  # type: ignore[override]
        return super().model_validate(obj)

    @staticmethod
    def _coerce_pm(v):
        if v is None:
            return None
        try:
            if hasattr(v, 'model_dump'):
                return v.model_dump()
        except Exception:
            return v
        return v

    @field_validator('proposed_metadata', mode='before')
    @classmethod
    def _validate_pm(cls, v):
        return cls._coerce_pm(v)


class CreateJob(InitJob):
    """Schema used by JobRepository.create_job for DB insertion.

    Inherits fields from InitJob and adds persistence defaults.
    """

    status: str = Field(default=JobStatus.PROCESSING.value)
    percent: Annotated[int, Field(default=0, strict=True, ge=0, le=100)]
    step: str | None = 'hash'


@dataclass(frozen=True, slots=True)
class JobCtx:
    """Immutable context passed between upload steps.

    Holds transient state for the upload pipeline; each step returns a new instance
    with updated fields to keep flows readable and testable.
    """

    # Identifiers and settings
    job_id: UUID
    collection: CollectionEnum
    file: TemporaryUploadFile
    hints: FinanceReportHints | NoopHints

    # Hashes/identifiers
    document_id: UUID
    digest: SHA256B64

    # Step outputs
    original_key: str | None = None
    markdown_key: str | None = None
    docs: list[Document] = field(default_factory=list)
    markdown_text: str | None = None
    skip_embed: bool | None = None

    metadata: dict | None = None
    proposed_metadata: ProposedMetadata | None = None
    needs_review: bool | None = False


class JobDocumentRefs(BaseModel):
    digest: SHA256B64
    collection: str
    document_uuid: UUID
