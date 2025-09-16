from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.metadata.schemas import ProposedMetadata
from app.schemas.upload import JobStatus
from app.utils.types import SHA256B64
from app.vector.models import IngestorSettings


class DocumentCreate(BaseModel):
    """Schema for creating a canonical Document row."""

    collection: str
    digest: SHA256B64
    original_filename: str
    content_type: str
    size_bytes: int
    meta: dict = Field(default_factory=dict)


class DocumentUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    original_uri: str | None = None
    markdown_uri: str | None = None
    store: str | None = None
    meta: Mapping[str, Any] | None = None


class JobCreate(BaseModel):
    status: JobStatus = Field(default=JobStatus.QUEUED)
    percent: int = Field(default=0)
    step: str | None = Field(default=None)
    document_id: UUID
    proposed_metadata: ProposedMetadata | None = None


class JobUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    ingestion_id: UUID | None = None
    status: JobStatus | None = None
    percent: int | None = None
    step: str | None = None
    proposed_metadata: ProposedMetadata | None = None


class IngestionVersion(BaseModel):
    chunker_model: str = Field(..., description='Semantic chunker name')
    chunker_version: str = Field(..., description='Semantic chunker version identifier')
    chunker_params: dict = Field(..., description='Semantic chunker parameters')
    embed_model: str = Field(..., description='Embedding model name')
    embed_model_version: str = Field(..., description='Embedding model version')
    embed_dim: int = Field(..., description='Embedding model output dimension')
    collection: str = Field(..., description='Logical collection scope')

    @classmethod
    def from_settings(cls, *, collection: str) -> 'IngestionVersion':
        settings = IngestorSettings().model_dump()
        return cls(**settings, collection=collection)

    def fingerprint(self) -> str:
        payload = self.model_dump(
            include={
                'chunker_model',
                'chunker_version',
                'chunker_params',
                'embed_model',
                'embed_model_version',
                'embed_dim',
                'collection',
            },
            mode='json',
        )
        canonical = json.dumps(payload, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(canonical.encode()).hexdigest()


class IngestionCreate(IngestionVersion):
    document_id: UUID
    job_id: UUID

    digest: SHA256B64 = Field(..., description='SHA-256 hex digest of the document')
    num_chunks: int = Field(0, description='Number of chunks produced by the chunker')

    @classmethod
    def create(cls, *, collection: str, document_id: UUID, digest: SHA256B64, job_id: UUID | None) -> 'IngestionCreate':
        ingestion_version = IngestionVersion.from_settings(collection=collection)
        return cls(**ingestion_version.model_dump(), document_id=document_id, job_id=job_id, digest=digest)


class IngestionResult(BaseModel):
    digest: SHA256B64
    collection: str
    total_docs: int
    batches: int
    ingestion_id: UUID | None = None
    skipped: bool = False
    reason: str | None = None
