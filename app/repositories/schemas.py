from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID
from typing import List

from app.utils.types import SHA256B64
from app.schemas.upload import JobStatus
from app.metadata.schemas import ProposedMetadata


@dataclass(frozen=True)
class DocumentCreate:
    """Schema for creating a canonical Document row.

    Encapsulates the inputs required to insert a document or return the
    existing canonical row keyed by (collection, digest).
    """

    collection: str
    digest: SHA256B64
    original_filename: str | None = None
    content_type: str | None = None
    size_bytes: int | None = None
    meta: dict | None = field(default=None)


@dataclass(frozen=True)
class JobProgressSnapshot:
    """Lightweight progress snapshot for repository boundary."""

    percent: int
    step: str | None


@dataclass(frozen=True)
class JobStatusSnapshot:
    """Domain type returned by repositories for job status queries.

    This is intentionally lightweight (no Pydantic) and suitable for
    internal use in services. API layers should map to DTOs.
    """

    job_id: UUID
    status: JobStatus | str
    progress: JobProgressSnapshot
    original_filename: str | None = None
    proposed_metadata: ProposedMetadata | None = None
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class JobDocumentRefs:
    """Minimal document references tied to a job for follow-up operations."""

    digest: SHA256B64
    collection: str
    document_uuid: UUID | None = None


@dataclass(frozen=True)
class CreateJobCmd:
    """Command object for creating a job at repository boundary."""

    status: JobStatus
    percent: int
    step: str | None
    digest: SHA256B64
    document_uuid: UUID
    collection: str
    original_filename: str | None
    content_type: str | None
    size_bytes: int | None
    proposed_metadata: ProposedMetadata | None = None
