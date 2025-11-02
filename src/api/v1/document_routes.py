from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlmodel.ext.asyncio.session import AsyncSession
from starlette.responses import Response
from tenauth.fastapi import require_auth

from core.deps import SessionDep
from schemas.documents import (
    DocumentFilenameUpdateRequest,
    DocumentListFilters,
    DocumentListResponse,
    DocumentResponse,
)
from services.document_service import DocumentService
from services.factory import get_document_service

router = APIRouter(
    prefix='/v1/documents',
    dependencies=[Depends(require_auth), Depends(SessionDep)],
)


@router.get('/{document_id}', response_model=DocumentResponse, tags=['documents'])
async def get_document(
    document_id: UUID,
    document_service: DocumentService = Depends(get_document_service),
    session: AsyncSession = Depends(SessionDep),
) -> DocumentResponse:
    """Retrieve a single document by its ID."""
    return await document_service.get_document(session, document_id=document_id)


@router.get('/', response_model=DocumentListResponse, tags=['documents'])
async def list_documents(
    filters: DocumentListFilters = Depends(DocumentListFilters),
    document_service: DocumentService = Depends(get_document_service),
    session: AsyncSession = Depends(SessionDep),
) -> DocumentListResponse:
    """List documents with optional filters and pagination."""
    return await document_service.list_documents(session, filters=filters)


@router.delete('/{document_id}', status_code=204, tags=['documents'])
async def delete_document(
    document_id: UUID,
    document_service: DocumentService = Depends(get_document_service),
    session: AsyncSession = Depends(SessionDep),
) -> Response:
    """Delete a document and its associated vectors and artifacts."""
    await document_service.delete(session, document_id=document_id)
    return Response(status_code=204)


@router.patch('/{document_id}/filename', response_model=DocumentResponse, tags=['documents'])
async def update_document_filename(
    document_id: UUID,
    payload: DocumentFilenameUpdateRequest,
    document_service: DocumentService = Depends(get_document_service),
    session: AsyncSession = Depends(SessionDep),
) -> DocumentResponse:
    """Update the canonical filename and sync embedding metadata."""
    return await document_service.update_original_filename(
        session,
        document_id=document_id,
        new_filename=payload.filename,
    )
