from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from utils.types import SHA256B64


class ChunkSearchRequest(BaseModel):
    collection: str = Field(default='default', min_length=1, max_length=255, description='Vector collection name')
    query: str = Field(..., min_length=1, description='Natural language query to embed')
    digest: SHA256B64
    limit: int = Field(default=10, ge=1, le=64)
    metadata_filter: dict[str, Any] | None = Field(
        default=None,
        description='Optional PGVector-style metadata filter appended to the digest constraint.',
    )
    exclude_chunk_ids: list[int | str] | None = Field(
        default=None,
        description='Chunk identifiers that should be excluded from the search results.',
    )
    score_threshold: float | None = Field(
        default=None,
        ge=0.0,
        description='Discard matches with a score lower than this threshold.',
    )

    def build_filter(self) -> dict[str, Any] | None:
        filters: list[dict[str, Any]] = [{'digest': {'$eq': self.digest}}]
        if self.metadata_filter:
            filters.append(self.metadata_filter)
        if self.exclude_chunk_ids:
            filters.append({'chunk_id': {'$nin': list(self.exclude_chunk_ids)}})
        if not filters:
            return None
        if len(filters) == 1:
            return filters[0]
        return {'$and': filters}


class ChunkSearchResult(BaseModel):
    chunk_id: str | None = Field(default=None, description='Identifier from metadata.chunk_id if present')
    text: str = Field(..., description='Chunk text content')
    metadata: dict[str, Any] = Field(default_factory=dict, description='Metadata attached to the chunk')
    score: float = Field(..., ge=0.0, description='Similarity score returned by PGVector')


class ChunkSearchResponse(BaseModel):
    results: list[ChunkSearchResult] = Field(default_factory=list, description='Ordered matches')
    collection_exists: bool = Field(
        default=True,
        description='False when the requested collection does not exist for the current tenant',
    )
