"""
init schema for documents, upload_jobs, ingestion_versions

Revision ID: 20250927_02_init_schema
Revises: 20250927_01_ensure_vector
Create Date: 2025-09-27 09:06:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20250927_02_init_schema"
down_revision = "20250927_01_ensure_vector"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # documents
    op.create_table(
        "documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False,
                  server_default=sa.text("current_setting('app.tenant_id', true)::uuid")),
        sa.Column("collection", sa.Text(), nullable=False),
        sa.Column("digest", sa.Text(), nullable=False),
        sa.Column("original_filename", sa.Text(), nullable=True),
        sa.Column("content_type", sa.Text(), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=True),
        sa.Column("original_uri", sa.Text(), nullable=True),
        sa.Column("markdown_uri", sa.Text(), nullable=True),
        sa.Column("store", sa.Text(), nullable=True),
        sa.Column("meta", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False,
                  server_default=sa.text("current_setting('app.user_id', true)::uuid")),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.UniqueConstraint("tenant_id", "collection", "digest", name="uq_documents_tenant_collection_digest"),
    )
    op.create_index("ix_documents_collection", "documents", ["collection"], unique=False)
    op.create_index("ix_documents_digest", "documents", ["digest"], unique=False)

    # upload_jobs (create without FK to ingestion_versions to avoid circular dependency)
    op.create_table(
        "upload_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False,
                  server_default=sa.text("current_setting('app.tenant_id', true)::uuid")),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ingestion_id", postgresql.UUID(as_uuid=True), nullable=True),  # FK added after table creation
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("percent", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("step", sa.Text(), nullable=True),
        sa.Column("proposed_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("warnings", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("errors", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False,
                  server_default=sa.text("current_setting('app.user_id', true)::uuid")),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index("ix_jobs_status", "upload_jobs", ["status"], unique=False)
    op.create_index(
        "uq_active_job_per_doc",
        "upload_jobs",
        ["tenant_id", "document_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('queued','processing')"),
    )

    # ingestion_versions (create without FK to upload_jobs to avoid circular dependency)
    op.create_table(
        "ingestion_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False,
                  server_default=sa.text("current_setting('app.tenant_id', true)::uuid")),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=True),  # FK added after table creation
        sa.Column("chunker_model", sa.Text(), nullable=False),
        sa.Column("chunker_version", sa.Text(), nullable=False),
        sa.Column("chunker_params", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("embed_model", sa.Text(), nullable=False),
        sa.Column("embed_model_version", sa.Text(), nullable=False),
        sa.Column("embed_dim", sa.Integer(), nullable=False),
        sa.Column("collection", sa.Text(), nullable=False),
        sa.Column("digest", sa.Text(), nullable=False),
        sa.Column("fingerprint", sa.Text(), nullable=False),
        sa.Column("num_chunks", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False,
                  server_default=sa.text("current_setting('app.user_id', true)::uuid")),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.UniqueConstraint("tenant_id", "document_id", "collection", "digest", name="uq_ingestion_compound"),
    )
    op.create_index("ix_ingestions_digest", "ingestion_versions", ["digest"], unique=False)
    op.create_index("ix_ingestions_fingerprint", "ingestion_versions", ["fingerprint"], unique=False)

    # Now add the circular foreign keys after both tables exist
    op.create_foreign_key(
        "fk_jobs_ingestion_id",
        source_table="upload_jobs",
        referent_table="ingestion_versions",
        local_cols=["ingestion_id"],
        remote_cols=["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_ingestions_job_id",
        source_table="ingestion_versions",
        referent_table="upload_jobs",
        local_cols=["job_id"],
        remote_cols=["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    # Drop tables (constraints will be dropped automatically with the tables)
    op.drop_index("uq_active_job_per_doc", table_name="upload_jobs")
    op.drop_index("ix_jobs_status", table_name="upload_jobs")
    op.drop_table("upload_jobs")

    op.drop_index("ix_ingestions_fingerprint", table_name="ingestion_versions")
    op.drop_index("ix_ingestions_digest", table_name="ingestion_versions")
    op.drop_table("ingestion_versions")

    op.drop_index("ix_documents_digest", table_name="documents")
    op.drop_index("ix_documents_collection", table_name="documents")
    op.drop_table("documents")
