from datetime import datetime
from typing import Any, List, Optional
from uuid import UUID

from pydantic import ConfigDict
from sqlalchemy import Column, ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.types import UserDefinedType
from sqlmodel import Field, Relationship, SQLModel, UniqueConstraint

from core.config import get_settings
from repositories.fields import (
    created_at_field,
    created_by_field,
    document_fk,
    ingestion_fk,
    job_fk,
    tenant_id_field,
    updated_at_field,
    updated_by_field,
    uuid_pk,
)

APP_SCHEMA = get_settings().db_schema


class VectorType(UserDefinedType):
    """Lightweight pgvector column descriptor for SQLModel metadata."""

    cache_ok = True

    def get_col_spec(self, **_: Any) -> str:
        return f'vector({get_settings().embedding.dim})'


class BaseSQLModel(SQLModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, from_attributes=True)  # type: ignore[bad-override]


class DocumentRecord(BaseSQLModel, table=True):
    __tablename__ = 'documents'  # type: ignore[bad-argument-type]
    __table_args__ = (
        UniqueConstraint(
            'tenant_id',
            'collection',
            'digest',
            name='uq_documents_tenant_collection_digest',
        ),
        {'schema': APP_SCHEMA},
    )

    id: UUID = uuid_pk()
    tenant_id: UUID = tenant_id_field()

    collection: str = Field(index=True)
    digest: str = Field(max_length=44, index=True)
    original_filename: str | None = None
    content_type: str | None = None
    size_bytes: int | None = None
    original_uri: str | None = None
    markdown_uri: str | None = None
    store: str | None = None
    meta: dict = Field(default_factory=dict, sa_column=Column(JSONB))

    created_at: datetime = created_at_field()
    updated_at: datetime = updated_at_field()
    created_by: UUID = created_by_field()
    updated_by: UUID | None = updated_by_field()

    # Relationships
    jobs: List['JobRecord'] = Relationship(
        back_populates='document',
        sa_relationship_kwargs={
            'cascade': 'all, delete, delete-orphan',
            'passive_deletes': True,
        },
    )
    ingestions: List['IngestionRecord'] = Relationship(
        back_populates='document',
        sa_relationship_kwargs={
            'cascade': 'all, delete, delete-orphan',
            'passive_deletes': True,
        },
    )


class JobRecord(BaseSQLModel, table=True):
    __tablename__ = 'upload_jobs'  # type: ignore[bad-argument-type]
    __table_args__ = (
        Index(
            'uq_active_job_per_doc',
            'tenant_id',
            'document_id',
            unique=True,
            postgresql_where=text("status IN ('queued','processing')"),
        ),
        {'schema': APP_SCHEMA},
    )

    id: UUID = uuid_pk()
    tenant_id: UUID = tenant_id_field()
    document_id: UUID = document_fk()
    ingestion_id: UUID | None = ingestion_fk(nullable=True)

    status: str = Field(index=True)
    percent: int = Field(default=0)
    step: str | None = None

    # ORM relationships
    document: DocumentRecord = Relationship(back_populates='jobs')
    # Link to the produced/reused ingestion (nullable; FK on Job)
    ingestion: Optional['IngestionRecord'] = Relationship(
        sa_relationship_kwargs={
            'uselist': False,
            'primaryjoin': 'JobRecord.ingestion_id==IngestionRecord.id',
            'foreign_keys': '[JobRecord.ingestion_id]',
            'passive_deletes': True,
        },
    )

    # JSONB columns for proposed metadata and messages
    proposed_metadata: dict = Field(default_factory=dict, sa_column=Column(JSONB))
    warnings: list = Field(default_factory=list, sa_column=Column(JSONB))
    errors: list = Field(default_factory=list, sa_column=Column(JSONB))

    created_at: datetime = created_at_field()
    updated_at: datetime = updated_at_field()
    created_by: UUID = created_by_field()
    updated_by: UUID | None = updated_by_field()


class IngestionRecord(BaseSQLModel, table=True):
    __tablename__ = 'ingestion_versions'  # type: ignore[bad-argument-type]
    __table_args__ = (
        UniqueConstraint(
            'tenant_id',
            'document_id',
            'collection',
            'digest',
            name='uq_ingestion_compound',
        ),
        {'schema': APP_SCHEMA},
    )

    id: UUID = uuid_pk()
    tenant_id: UUID = tenant_id_field()
    document_id: UUID = document_fk()
    job_id: UUID | None = job_fk(nullable=True)

    chunker_model: str
    chunker_version: str
    chunker_params: dict = Field(default_factory=dict, sa_column=Column(JSONB))
    embed_model: str
    embed_model_version: str
    embed_dim: int
    collection: str
    digest: str = Field(max_length=44, index=True)
    parser_fp: str = Field(index=True)
    chunker_fp: str = Field(index=True)
    embedding_fp: str = Field(index=True)
    num_chunks: int

    created_at: datetime = created_at_field()
    updated_at: datetime = updated_at_field()
    created_by: UUID = created_by_field()
    updated_by: UUID | None = updated_by_field()

    # Relationships
    document: DocumentRecord = Relationship(back_populates='ingestions')
    # Provenance: which job created this ingestion (separate relationship, no back_populates)
    job: Optional[JobRecord] = Relationship(
        sa_relationship_kwargs={
            'uselist': False,
            'primaryjoin': 'IngestionRecord.job_id==JobRecord.id',
            'foreign_keys': '[IngestionRecord.job_id]',
        },
    )


class LangChainEmbedding(BaseSQLModel, table=True):
    """SQLModel metadata for the partitioned langchain_pg_embedding table."""

    __tablename__ = 'langchain_pg_embedding'  # type: ignore[assignment]
    __table_args__ = ({'schema': APP_SCHEMA, 'postgresql_partition_by': 'LIST (tenant_id)'},)

    id: str = Field(sa_column=Column(String, primary_key=True))
    tenant_id: UUID = Field(
        sa_column=Column(
            PGUUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=text("current_setting('app.tenant_id', true)::uuid"),
        )
    )
    collection_id: UUID | None = Field(
        default=None,
        sa_column=Column(
            PGUUID(as_uuid=True),
            ForeignKey(f'{APP_SCHEMA}.langchain_pg_collection.uuid', ondelete='CASCADE'),
            nullable=True,
        ),
    )
    embedding: list[float] | None = Field(default=None, sa_column=Column(VectorType(), nullable=True))
    document: str | None = Field(default=None, sa_column=Column(String, nullable=True))
    cmetadata: dict | None = Field(default=None, sa_column=Column(JSONB, nullable=True))
