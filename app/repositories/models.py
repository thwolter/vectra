from __future__ import annotations

from datetime import datetime, timezone
import uuid
from uuid import uuid4

from sqlmodel import Field, SQLModel, UniqueConstraint
from sqlalchemy import Column, DateTime
from sqlalchemy.dialects.postgresql import JSONB, UUID


class Document(SQLModel, table=True):
    """Canonical documents table keyed by (collection, binary_hash).

    Stores immutable original_filename (first-seen wins) and basic attributes.
    """

    __tablename__ = 'documents'
    __table_args__ = (
        UniqueConstraint('collection', 'digest', name='uq_documents_collection_digest'),
    )

    id: uuid.UUID = Field(
        default_factory=uuid4,
        sa_column=Column(UUID(as_uuid=True), primary_key=True, nullable=False),
    )
    collection: str = Field(index=True)
    digest: str = Field(index=True, max_length=44)
    original_filename: str | None = Field(default=None)
    content_type: str | None = Field(default=None)
    size_bytes: int | None = Field(default=None)
    original_uri: str | None = Field(default=None)
    markdown_uri: str | None = Field(default=None)
    store: str | None = Field(default=None)
    meta: dict | None = Field(default=None, sa_column=Column(JSONB))
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class IngestionVersion(SQLModel, table=True):
    """SQLModel representation of the ingestion_versions table.

    Uniqueness is enforced across the tuple:
    (collection, source, content_fp, chunker_version, embed_model, embed_model_ver)
    """

    __tablename__ = 'ingestion_versions'
    __table_args__ = (
        UniqueConstraint(
            'collection',
            'digest',
            'chunker_version',
            'embed_model',
            'embed_model_ver',
            name='uq_ingestion_versions_composite',
        ),
    )

    id: uuid.UUID = Field(
        default_factory=uuid4,
        sa_column=Column(UUID(as_uuid=True), primary_key=True, nullable=False),
    )
    collection: str = Field(index=True)
    digest: str = Field(index=True, max_length=44)
    chunker_version: str
    embed_model: str
    embed_model_ver: str
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class JobRecord(SQLModel, table=True):
    """SQLModel table for tracking upload job statuses.

    Linkage:
    - document_uuid: UUID of the canonical row in `documents` (DB-local PK).
    - digest: deterministic hex digest used for vector and idempotency.
    Mirrors collection and binary_hash for observability and joins.
    """

    __tablename__ = 'upload_jobs'

    job_id: uuid.UUID = Field(
        default_factory=uuid4,
        sa_column=Column(UUID(as_uuid=True), primary_key=True, nullable=False),
    )
    status: str = Field(index=True)
    percent: int = Field(default=0)
    step: str | None = Field(default=None)

    # Linkage to Document
    document_uuid: uuid.UUID | None = Field(default=None, index=True)
    collection: str | None = Field(default=None, index=True)
    digest: str | None = Field(default=None, index=True, max_length=44)

    # Descriptive fields
    original_filename: str | None = Field(default=None)
    content_type: str | None = Field(default=None)
    size_bytes: int | None = Field(default=None)

    # JSONB columns for proposed metadata and messages
    proposed_metadata: dict | None = Field(default=None, sa_column=Column(JSONB))
    warnings: list[str] = Field(default_factory=list, sa_column=Column(JSONB))
    errors: list[str] = Field(default_factory=list, sa_column=Column(JSONB))
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
