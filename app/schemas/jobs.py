from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from langchain_core.documents import Document

from app.api.file import TemporaryUploadFile
from app.metadata.schemas import FinanceReportHints, NoopHints, ProposedMetadata
from app.schemas.enums import CollectionEnum
from app.utils.types import SHA256B64


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
