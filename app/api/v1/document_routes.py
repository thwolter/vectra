from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlmodel.ext.asyncio.session import AsyncSession
from starlette.responses import Response

from app.core.dependencies import access_scoped_session
from app.schemas.documents import DocumentListResponse, DocumentResponse
from app.services.document_service import DocumentService
from app.services.factory import get_document_service

router = APIRouter(prefix='/v1/documents')


@router.get('/{document_id}', response_model=DocumentResponse, tags=['documents'])
async def get_document(
    document_id: UUID,
    document_service: DocumentService = Depends(get_document_service),
    session: AsyncSession = Depends(access_scoped_session),
) -> DocumentResponse:
    """Retrieve a single document by its ID."""
    return await document_service.get_document(session, document_id=document_id)


@router.get('/', response_model=DocumentListResponse, tags=['documents'])
async def list_documents(
    filters: dict,
    document_service: DocumentService = Depends(get_document_service),
    session: AsyncSession = Depends(access_scoped_session),
) -> DocumentListResponse:
    """List documents with optional filters and pagination."""
    return await document_service.list_documents(session, filters=filters)


@router.delete('/{document_id}', status_code=204, tags=['documents'])
async def delete_document(
    document_id: UUID,
    document_service: DocumentService = Depends(get_document_service),
    session: AsyncSession = Depends(access_scoped_session),
) -> Response:
    """Delete a document and its associated vectors and artifacts."""
    await document_service.delete(session, document_id=document_id)
    return Response(status_code=204)
