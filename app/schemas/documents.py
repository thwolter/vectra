from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.embedding import DocumentChunk, DocumentContent
from app.utils.types import SHA256B64


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    digest: SHA256B64
    metadata: dict = Field(default={}, alias='meta')
    created_at: datetime
    created_by: UUID
    updated_at: datetime


class DocumentListResponse(BaseModel):
    items: List[DocumentResponse] = Field(default_factory=list)
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


class ProcessedDocument(BaseModel):
    """A processed document with its chunks."""

    original_content: DocumentContent = Field(..., description='Original content of the document')
    chunks: List[DocumentChunk] = Field(..., description='Chunks of the document')
    total_chunks: int = Field(..., description='Total number of chunks')


class BaseResponse(BaseModel):
    """Base response model for API endpoints."""

    success: bool = Field(..., description='Whether the operation was successful')
    message: str = Field(..., description='Message describing the result of the operation')


class ErrorResponse(BaseResponse):
    """Error response model for API endpoints."""

    success: bool = Field(False, description='Operation was not successful')
    error_code: str | None = Field(None, description='Error code')
    details: Optional[Dict[str, Any]] = Field(None, description='Additional error details')


class UploadResponse(BaseResponse):
    """Response model for file upload endpoint."""

    success: bool = Field(True, description='Operation was successful')
