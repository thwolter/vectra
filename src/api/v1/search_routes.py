from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from loguru import logger
from tenauth.fastapi import require_access_context, require_auth
from tenauth.schemas import AccessContext

from schemas.search import ChunkSearchRequest, ChunkSearchResponse
from services.factory import get_retrieval_service
from services.retrieval_service import RetrievalService

router = APIRouter(
    prefix='/v1/search',
    tags=['search'],
    dependencies=[Depends(require_auth)],
)


@router.post('/chunks', response_model=ChunkSearchResponse, tags=['search'])
async def search_chunks(
    payload: ChunkSearchRequest,
    retrieval_service: RetrievalService = Depends(get_retrieval_service),
    access: AccessContext = Depends(require_access_context),
) -> ChunkSearchResponse:
    try:
        return await retrieval_service.search(payload=payload, access=access)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.exception('vectra chunk search failed')
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail='chunk search failed') from exc
