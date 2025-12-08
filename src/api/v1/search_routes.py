from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from loguru import logger
from sqlmodel.ext.asyncio.session import AsyncSession
from tenauth.fastapi import require_access_context, require_auth
from tenauth.schemas import AccessContext

from core.deps import SessionDep
from repositories.exceptions import RecordNotFoundError
from schemas.documents import DocumentResponse
from schemas.search import ChunkSearchRequest, ChunkSearchResponse, DocumentAvailabilityRequest
from services.document_service import DocumentService
from services.factory import get_document_service, get_retrieval_service
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


@router.post('/document-availability', response_model=DocumentResponse, tags=['search'])
async def check_document_availability(
    payload: DocumentAvailabilityRequest,
    document_service: DocumentService = Depends(get_document_service),
    session: AsyncSession = Depends(SessionDep),
) -> DocumentResponse:
    """Confirm whether a document exists for the provided identifier and collection."""
    try:
        if payload.document_id:
            document = await document_service.get_document(session, document_id=payload.document_id)
            if document.collection != payload.collection:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f'Document {payload.document_id} does not belong to collection {payload.collection}',
                )
            if payload.digest and document.digest != payload.digest:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f'Digest {payload.digest} does not match document {payload.document_id}',
                )
            return document
        assert payload.digest is not None
        return await document_service.get_document_by_digest(
            session,
            digest=payload.digest,
            collection=payload.collection,
        )
    except RecordNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Document not found') from exc
