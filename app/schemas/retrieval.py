from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, conint


class QueryRequest(BaseModel):
    query: str = Field(..., description='User query string')
    collection: Optional[str] = Field(None, description='Collection scope')
    source: Optional[str] = Field(None, description='Optional source filter')
    top_k: conint(ge=1, le=100) | None = Field(default=10, description='Max results to return')
    hybrid: bool = Field(False, description='Enable hybrid (sparse+dense) search')


class QueryHit(BaseModel):
    chunk_id: str
    document_id: str
    score: float
    content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class QueryResponse(BaseModel):
    query: str
    hits: List[QueryHit] = Field(default_factory=list)
    used_hybrid: bool = False


class MultiQueryRequest(BaseModel):
    query: str
    strategies: List[str] | None = Field(None, description='Optional list of strategy names to apply')
    top_k: conint(ge=1, le=100) | None = Field(default=10)
    collection: Optional[str] = None


class MultiQueryResponse(BaseModel):
    query: str
    subqueries: List[str] = Field(default_factory=list)
    hits: List[QueryHit] = Field(default_factory=list)


class ChunkDetail(BaseModel):
    chunk_id: str
    document_id: str
    content: str
    index: int
    provenance: Dict[str, Any] = Field(
        default_factory=dict,
        description='Full provenance including S3 URIs, parser, page range, etc.',
    )


class ListChunksResponse(BaseModel):
    document_id: str
    items: List[ChunkDetail] = Field(default_factory=list)
    next_page_token: str | None = None
