from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import Column, DateTime, ForeignKey, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlmodel import Field

from core.config import get_settings

APP_SCHEMA = get_settings().app_schema


def uuid_pk() -> Any:
    """Primary key UUID field using SQLModel Field with underlying PG UUID column."""
    return Field(sa_column=Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4))


def document_fk(nullable: bool = False) -> Any:
    """Nullable FK to documents.id with ondelete CASCADE and index."""
    return Field(
        default=None,
        sa_column=Column(
            PGUUID(as_uuid=True),
            ForeignKey(f'{APP_SCHEMA}.documents.id', ondelete='CASCADE'),
            nullable=nullable,
            index=True,
        ),
    )


def job_fk(nullable: bool = False) -> Any:
    """FK to upload_jobs.id with ondelete SET NULL (so deleting a job does not delete the ingestion)."""
    return Field(
        default=None,
        sa_column=Column(
            PGUUID(as_uuid=True),
            ForeignKey(f'{APP_SCHEMA}.upload_jobs.id', ondelete='SET NULL', name='fk_ingestions_job_id'),
            nullable=nullable,
        ),
    )


def ingestion_fk(nullable: bool = False) -> Any:
    """FK to ingestion_versions.id with ondelete SET NULL (so deleting an ingestion does not delete the job)."""
    return Field(
        default=None,
        sa_column=Column(
            PGUUID(as_uuid=True),
            ForeignKey(f'{APP_SCHEMA}.ingestion_versions.id', ondelete='SET NULL', name='fk_jobs_ingestion_id'),
            nullable=nullable,
            index=True,
        ),
    )


def tenant_id_field() -> Any:
    """Tenant id column populated from PostgreSQL setting app.tenant_id."""
    return Field(
        sa_column=Column(
            PGUUID(as_uuid=True),
            nullable=False,
            server_default=text("current_setting('app.tenant_id', true)::uuid"),
        )
    )


def created_at_field() -> Any:
    """UTC created_at timestamp with default now()."""
    return Field(
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            default=lambda: datetime.now(timezone.utc),
        )
    )


def updated_at_field() -> Any:
    """UTC updated_at timestamp with server default now()."""
    return Field(
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            onupdate=lambda: datetime.now(timezone.utc),
        )
    )


def created_by_field() -> Any:
    """Created by user UUID sourced from PostgreSQL setting app.user_id."""
    return Field(
        sa_column=Column(
            PGUUID(as_uuid=True),
            nullable=False,
            server_default=text("current_setting('app.user_id', true)::uuid"),
        )
    )


def updated_by_field() -> Any:
    """Updated by user UUID sourced from PostgreSQL setting app.user_id."""
    return Field(
        sa_column=Column(
            PGUUID(as_uuid=True),
            nullable=True,
            onupdate=text("current_setting('app.user_id', true)::uuid"),
        )
    )
