from __future__ import annotations

from typing import TYPE_CHECKING, Any, Mapping
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from core.config import get_settings
from schemas.upload import JobStatus
from utils.types import SHA256B64

if TYPE_CHECKING:
    from repositories.models import IngestionRecord


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


class JobUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    ingestion_id: UUID | None = None
    status: JobStatus | None = None
    percent: int | None = None
    step: str | None = None


class IngestionPlan(BaseModel):
    parser_changed: bool
    chunker_changed: bool
    embedding_changed: bool

    @property
    def run_parser(self) -> bool:
        return self.parser_changed

    @property
    def run_chunker(self) -> bool:
        return self.parser_changed or self.chunker_changed

    @property
    def run_embedding(self) -> bool:
        return self.parser_changed or self.chunker_changed or self.embedding_changed


class IngestionVersion(BaseModel):
    collection: str
    parser_fp: str
    chunker_fp: str
    embedding_fp: str

    @classmethod
    def from_settings(cls, *, collection: str) -> 'IngestionVersion':
        settings = get_settings()
        return cls(
            collection=collection,
            parser_fp=settings.llama_cloud.get_fingerprint(),
            chunker_fp=settings.text_splitter.get_fingerprint(),
            embedding_fp=settings.embedding.get_fingerprint(),
        )

    def matches(self, record: IngestionRecord | None) -> bool:
        if record is None:
            return False
        return (
            record.parser_fp == self.parser_fp
            and record.chunker_fp == self.chunker_fp
            and record.embedding_fp == self.embedding_fp
        )

    def plan_for(self, record: IngestionRecord | None) -> IngestionPlan:
        if record is None:
            return IngestionPlan(parser_changed=True, chunker_changed=True, embedding_changed=True)

        parser_changed = record.parser_fp != self.parser_fp
        chunker_changed = record.chunker_fp != self.chunker_fp
        embedding_changed = record.embedding_fp != self.embedding_fp

        return IngestionPlan(
            parser_changed=parser_changed,
            chunker_changed=parser_changed or chunker_changed,
            embedding_changed=parser_changed or chunker_changed or embedding_changed,
        )


class IngestionCreate(BaseModel):
    document_id: UUID
    job_id: UUID

    digest: SHA256B64 = Field(..., description='SHA-256 hex digest of the document')
    num_chunks: int = Field(0, description='Number of chunks produced by the chunker')

    chunker_model: str = Field(..., description='Semantic chunker name')
    chunker_version: str = Field(..., description='Semantic chunker version identifier')
    chunker_params: dict = Field(..., description='Semantic chunker parameters')
    embed_model: str = Field(..., description='Embedding model name')
    embed_model_version: str = Field(..., description='Embedding model version')
    embed_dim: int = Field(..., description='Embedding model output dimension')
    collection: str = Field(..., description='Logical collection scope')

    parser_fp: str = Field(..., description='Fingerprint of the parser used for document ingestion')
    chunker_fp: str = Field(..., description='Fingerprint of the chunker used for document ingestion')
    embedding_fp: str = Field(..., description='Fingerprint of the embedding model used for document ingestion')

    @classmethod
    def create(
        cls, *, collection: str, document_id: UUID, digest: SHA256B64, job_id: UUID | None, num_chunks: int = 0
    ) -> 'IngestionCreate':
        settings = get_settings()
        version = IngestionVersion.from_settings(collection=collection)
        return cls(
            document_id=document_id,
            job_id=job_id,
            digest=digest,
            chunker_model=settings.text_splitter.chunker,
            chunker_version=settings.text_splitter.version,
            chunker_params={},
            embed_model=settings.embedding.model,
            embed_model_version=settings.embedding.version,
            embed_dim=settings.embedding.dim,
            collection=collection,
            parser_fp=version.parser_fp,
            chunker_fp=version.chunker_fp,
            embedding_fp=version.embedding_fp,
            num_chunks=num_chunks,
        )

    def version(self, *, collection: str | None = None) -> 'IngestionVersion':
        return IngestionVersion(
            collection=collection or self.collection,
            parser_fp=self.parser_fp,
            chunker_fp=self.chunker_fp,
            embedding_fp=self.embedding_fp,
        )


class IngestionResult(BaseModel):
    digest: SHA256B64
    collection: str
    total_docs: int
    batches: int
    ingestion_id: UUID | None = None
    skipped: bool = False
    reason: str | None = None
