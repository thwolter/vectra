from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Path, Query

from app.schemas.retrieval import (
    ChunkDetail,
    ListChunksResponse,
    MultiQueryRequest,
    MultiQueryResponse,
    QueryRequest,
    QueryResponse,
)

router = APIRouter(prefix='/v1/retrieval', tags=['retrieval'])


@router.post('/query', response_model=QueryResponse)
async def retrieval_query(payload: QueryRequest) -> QueryResponse:
    """Vector/hybrid search over chunks.

    For now, this is a placeholder route returning 501 Not Implemented
    to make the contract visible. The implementation will be provided later.
    """
    # Minimal placeholder to satisfy route existence
    raise HTTPException(status_code=501, detail='Retrieval query not implemented yet')


@router.post('/mquery', response_model=MultiQueryResponse)
async def retrieval_multi_query(payload: MultiQueryRequest) -> MultiQueryResponse:
    """Multi-query retrieval (e.g., rephrase, ensemble).

    Placeholder returning 501 Not Implemented.
    """
    raise HTTPException(status_code=501, detail='Multi-query retrieval not implemented yet')


@router.get('/chunks/{chunk_id}', response_model=ChunkDetail)
async def get_chunk_detail(
    chunk_id: str = Path(..., description='Unique chunk identifier'),
) -> ChunkDetail:
    """Fetch a single chunk with full provenance.

    Placeholder returning 501 Not Implemented.
    """
    raise HTTPException(status_code=501, detail='Chunk detail not implemented yet')


@router.get('/documents/{document_id}/chunks', response_model=ListChunksResponse)
async def list_document_chunks(
    document_id: str,
    page_token: Optional[str] = Query(None, description='Opaque pagination token'),
    page_size: int = Query(50, ge=1, le=200, description='Page size (1-200)'),
) -> ListChunksResponse:
    """List chunks for one document (paginated).

    Placeholder returning 501 Not Implemented.
    """
    raise HTTPException(status_code=501, detail='List document chunks not implemented yet')
