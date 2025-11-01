from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, ClassVar, Dict, List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from schemas.embedding import DocumentChunk, DocumentContent
from utils.types import SHA256B64


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    digest: SHA256B64
    collection: str
    original_filename: str | None = None
    content_type: str | None = None
    size_bytes: int | None = None
    original_uri: str | None = None
    markdown_uri: str | None = None
    metadata: dict = Field(default={}, alias='meta')
    created_at: datetime
    created_by: UUID
    updated_at: datetime


class DocumentListFilters(BaseModel):
    """Query parameters accepted by the document listing endpoint."""

    model_config = ConfigDict(populate_by_name=True, extra='forbid')

    query: str | None = Field(default=None)
    kind: str | None = Field(default=None)
    limit: int | None = Field(default=None, ge=1, le=100)
    offset: int | None = Field(default=None, ge=0)
    next_page_token: str | None = Field(default=None, alias='nextPageToken')

    DEFAULT_LIMIT: ClassVar[int] = 20

    @model_validator(mode='after')
    def _validate_pagination(self) -> 'DocumentListFilters':
        if self.next_page_token is not None:
            try:
                int(self.next_page_token)
            except ValueError as exc:  # pragma: no cover - defensive branch
                raise ValueError('nextPageToken must be an integer string') from exc
        return self

    @property
    def effective_limit(self) -> int:
        """Return a sanitized limit with a sensible default."""
        return self.limit or self.DEFAULT_LIMIT

    @property
    def effective_offset(self) -> int:
        """Resolve the offset, preferring the token when provided."""
        if self.next_page_token is not None:
            return int(self.next_page_token)
        return self.offset or 0

    def to_repo_filters(self, *, collection: str | None = None) -> dict[str, Any]:
        """Render filters suitable for repository queries."""
        repo_filters: dict[str, Any] = {
            'query': self.query,
            'kind': self.kind,
            'limit': self.effective_limit,
            'offset': self.effective_offset,
        }
        if collection:
            repo_filters['collection'] = collection
        return repo_filters


class DocumentListResponse(BaseModel):
    items: List[DocumentResponse] = Field(default_factory=list)
    next_page_token: str | None = None


OriginalFilename = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class DocumentFilenameUpdateRequest(BaseModel):
    original_filename: OriginalFilename = Field(
        ...,
        description='New filename to persist on the document and embedding metadata',
    )


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
