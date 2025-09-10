from __future__ import annotations

from typing import Any, Dict, List, Optional, Literal, Annotated
from pydantic import BaseModel, Field


class DocumentRef(BaseModel):
    id: str = Field(..., alias='document_id')
    legal_name: Optional[str] = Field(
        None, description='Company legal name (denormalized)'
    )
    company_id: str | None = Field(None)
    doc_type: str | None = None
    reporting_year: Optional[int] = None
    language: str | None = None
    pages: Optional[int] = None
    digest: str | None = None
    file_uri: str | None = None
    parser_profile: str | None = None
    parser_version: str | None = None
    embedding_profile: str | None = None
    embedding_dim: Optional[int] = None
    quality_score: Annotated[float, Field(default=0, strict=True, ge=0, le=100)]
    validation_status: Optional[
        Literal['auto_validated', 'validated', 'needs_review']
    ] = None
    scope: Optional[Literal['private', 'shared_request', 'shared']] = None
    version: Optional[int] = None
    created_at: str | None = None


class DocumentListResponse(BaseModel):
    items: List[DocumentRef] = Field(default_factory=list)
    next_page_token: str | None = None


class ReparseRequest(BaseModel):
    parser_profile: str | None = Field(None)
    reason: str | None = Field(None)
    dry_run: Optional[bool] = Field(False)


class ReembedRequest(BaseModel):
    embedding_profile: str | None = Field(None)
    reason: str | None = Field(None)


class ParserProfileInfo(BaseModel):
    name: str
    desc: str | None = None
    cost_tier: Optional[Literal['low', 'medium', 'high']] = None
    ocr: Optional[Literal['never', 'auto', 'always']] = 'auto'


class EmbeddingProfileInfo(BaseModel):
    name: str
    dim: Optional[int] = None
    desc: str | None = None


class ProfilesResponse(BaseModel):
    parsers: List[ParserProfileInfo] = Field(default_factory=list)
    embeddings: List[EmbeddingProfileInfo] = Field(default_factory=list)


# ---- Legacy models merged from app.models ----


class DocumentContent(BaseModel):
    """Content of a document."""

    content: str = Field(..., description='Text content of the document')
    metadata: dict = Field(..., description='Metadata of the document')


class DocumentChunk(BaseModel):
    """A chunk of a document with its metadata."""

    content: str = Field(..., description='Text content of the chunk')
    metadata: Dict[str, Any] = Field(..., description='Metadata of the chunk')
    chunk_id: str = Field(..., description='Unique identifier for the chunk')
    chunk_index: int = Field(..., description='Index of the chunk in the document')


class ProcessedDocument(BaseModel):
    """A processed document with its chunks."""

    original_content: DocumentContent = Field(
        ..., description='Original content of the document'
    )
    chunks: List[DocumentChunk] = Field(..., description='Chunks of the document')
    total_chunks: int = Field(..., description='Total number of chunks')


class BaseResponse(BaseModel):
    """Base response model for API endpoints."""

    success: bool = Field(..., description='Whether the operation was successful')
    message: str = Field(
        ..., description='Message describing the result of the operation'
    )


class ErrorResponse(BaseResponse):
    """Error response model for API endpoints."""

    success: bool = Field(False, description='Operation was not successful')
    error_code: str | None = Field(None, description='Error code')
    details: Optional[Dict[str, Any]] = Field(
        None, description='Additional error details'
    )


class UploadResponse(BaseResponse):
    """Response model for file upload endpoint."""

    success: bool = Field(True, description='Operation was successful')
