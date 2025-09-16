from __future__ import annotations

from typing import Any, Dict, Literal, Set
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from starlette.responses import StreamingResponse

from app.services.dependencies import get_document_service
from app.services.document_service import DocumentService

streaming_router = APIRouter(prefix='/v1/documents')


# OpenAPI: declare binary streaming so Swagger UI doesn't try to show JSON
BINARY_RESPONSE_SPEC: Dict[int | str, Dict[str, Any]] = {
    200: {
        'description': 'Binary file stream',
        'content': {
            'application/octet-stream': {'schema': {'type': 'string', 'format': 'binary'}},
            # Common specialised types (actual runtime media_type is set from metadata)
            'application/pdf': {'schema': {'type': 'string', 'format': 'binary'}},
            'text/markdown': {'schema': {'type': 'string', 'format': 'binary'}},
        },
    }
}

# Media types that browsers commonly render inline
ALLOW_INLINE_MEDIA_TYPES: Set[str] = {
    'application/pdf',
    'image/png',
    'image/jpeg',
    'image/gif',
    'image/webp',
}


# Internal helper to avoid duplicate response-building code
async def _stream_document_file_impl(
    *,
    document_id: UUID,
    which: Literal['original', 'markdown'],
    disposition: str,
    filename: str | None,
    document_service: DocumentService,
):
    try:
        streamer, meta, key = await document_service.stream_file(document_id, which)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail='File not found')

    headers: dict[str, str] = {}
    if meta.content_encoding:
        headers['Content-Encoding'] = meta.content_encoding
    if meta.size:
        headers['Content-Length'] = str(meta.size)

    # Only honour inline for media types typically renderable by browsers
    requested_inline = disposition == 'inline'
    effective_inline = requested_inline and (meta.content_type in ALLOW_INLINE_MEDIA_TYPES)

    # Provide a stable default filename if not provided
    if not filename:
        name = key.split('/')[-1]
        filename = name

    if effective_inline:
        headers['Content-Disposition'] = f'inline; filename="{filename}"'
    else:
        headers['Content-Disposition'] = f'attachment; filename="{filename}"'

    media_type = meta.content_type or 'application/octet-stream'
    return StreamingResponse(streamer, media_type=media_type, headers=headers)


@streaming_router.get(
    '/{document_id}/file/original',
    tags=['documents'],
    responses=BINARY_RESPONSE_SPEC,
    response_model=None,
)
async def stream_original_file(
    document_id: UUID,
    disposition: str = Query('inline', pattern='^(inline|attachment)$'),
    filename: str | None = Query(None, description='Optional filename for attachment'),
    document_service: DocumentService = Depends(get_document_service),
):
    """Stream the original uploaded file for a document."""
    return await _stream_document_file_impl(
        document_id=document_id,
        which='original',
        disposition=disposition,
        filename=filename,
        document_service=document_service,
    )


@streaming_router.get(
    '/{document_id}/file/markdown',
    tags=['documents'],
    responses=BINARY_RESPONSE_SPEC,
    response_model=None,
)
async def stream_markdown_file(
    document_id: UUID,
    disposition: str = Query('inline', pattern='^(inline|attachment)$'),
    filename: str | None = Query(None, description='Optional filename for attachment'),
    document_service: DocumentService = Depends(get_document_service),
):
    """Stream the normalized Markdown copy for a document."""
    return await _stream_document_file_impl(
        document_id=document_id,
        which='markdown',
        disposition=disposition,
        filename=filename,
        document_service=document_service,
    )
