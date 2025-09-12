from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel, UniqueConstraint
from sqlalchemy import Column, DateTime, text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID

from utils.types import SHA256B64


class DocumentRecord(SQLModel, table=True):
    """Canonical documents table keyed by (collection, binary_hash).

    Stores immutable original_filename (first-seen wins) and basic attributes.
    """

    __tablename__ = 'documents'
    __table_args__ = (
        UniqueConstraint(
            'tenant_id',
            'collection',
            'digest',
            name='uq_documents_tenant_collection_digest',
        ),
    )

    id: UUID = Field(
        default_factory=uuid4,
        sa_column=Column(PGUUID(as_uuid=True), primary_key=True, nullable=False),
    )
    tenant_id: UUID = Field(
        sa_column=Column(
            PGUUID(as_uuid=True),
            nullable=False,
            server_default=text("current_setting('app.tenant_id', true)::uuid"),
        )
    )
    collection: str = Field(index=True)
    digest: SHA256B64 = Field(index=True)
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
    updated_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            server_default=text("timezone('utc', now())"),
        )
    )
    created_by: UUID = Field(
        sa_column=Column(
            PGUUID(as_uuid=True),
            nullable=False,
            index=True,
            server_default=text("current_setting('app.user_id', true)::uuid"),
        )
    )


class IngestionRecord(SQLModel, table=True):
    """SQLModel representation of the ingestion_versions table.

    Uniqueness is enforced across the tuple:
    (collection, source, content_fp, chunker_version, embed_model, embed_model_ver)
    """

    __tablename__ = 'ingestion_versions'
    __table_args__ = (
        UniqueConstraint(
            'tenant_id',
            'collection',
            'digest',
            'chunker_version',
            'embed_model',
            'embed_model_ver',
            name='uq_ingestion_versions_tenant_composite',
        ),
    )

    id: UUID = Field(
        default_factory=uuid4,
        sa_column=Column(PGUUID(as_uuid=True), primary_key=True, nullable=False),
    )
    tenant_id: UUID = Field(
        sa_column=Column(
            PGUUID(as_uuid=True),
            nullable=False,
            server_default=text("current_setting('app.tenant_id', true)::uuid"),
        )
    )
    collection: str = Field(index=True)
    digest: SHA256B64 = Field(index=True)
    chunker_version: str
    embed_model: str
    embed_model_ver: str
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            server_default=text("timezone('utc', now())"),
        )
    )
    created_by: UUID = Field(
        sa_column=Column(
            PGUUID(as_uuid=True),
            nullable=False,
            index=True,
            server_default=text("current_setting('app.user_id', true)::uuid"),
        )
    )


class JobRecord(SQLModel, table=True):
    """SQLModel table for tracking upload job statuses.

    Linkage:
    - document_uuid: UUID of the canonical row in `documents` (DB-local PK).
    - digest: deterministic hex digest used for vector and idempotency.
    Mirrors collection and binary_hash for observability and joins.
    """

    __tablename__ = 'upload_jobs'

    id: UUID = Field(
        default_factory=uuid4,
        sa_column=Column(PGUUID(as_uuid=True), primary_key=True, nullable=False),
    )
    tenant_id: UUID = Field(
        sa_column=Column(
            PGUUID(as_uuid=True),
            nullable=False,
            server_default=text("current_setting('app.tenant_id', true)::uuid"),
        )
    )
    status: str = Field(index=True)
    percent: int = Field(default=0)
    step: str | None = Field(default=None)

    # Linkage to Document
    document_uuid: UUID | None = Field(default=None, index=True)
    collection: str = Field(index=True)
    digest: str = Field(index=True, max_length=44)

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
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            server_default=text("timezone('utc', now())"),
        )
    )
    created_by: UUID = Field(
        sa_column=Column(
            PGUUID(as_uuid=True),
            nullable=False,
            index=True,
            server_default=text("current_setting('app.user_id', true)::uuid"),
        )
    )
