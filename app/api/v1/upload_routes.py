from __future__ import annotations

from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    UploadFile,
    BackgroundTasks,
    Form,
    HTTPException,
    status,
)

from app.api.file import TemporaryUploadFile
from app.api.utils import parse_hints_from_any
from app.api.schemas import AccessContext
from app.protocols.services import UploadServiceProtocol
from app.services.factory import get_upload_service
from app.schemas.upload import (
    UploadInitResponse,
    StartUploadInput,
    ContinueProcessingInput,
)
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.dependencies import access_scoped_session


# Hard limits to protect memory/CPU. Adjust via settings if needed.
MAX_UPLOAD_SIZE = 50 * 1024 * 1024  # 50 MB
READ_CHUNK_SIZE = 1024 * 1024  # 1 MB

router = APIRouter(prefix='/v1')


@router.post(
    '/uploads',
    response_model=UploadInitResponse,
    status_code=201,
    tags=['uploads'],
    responses={
        413: {'description': 'Uploaded file too large'},
        415: {'description': 'Unsupported media type'},
    },
)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: Annotated[
        UploadFile, File(description='Document to upload (PDF, DOCX, etc.)')
    ],
    hints: Annotated[
        str | None, Form(description='Optional hints for document parsing')
    ] = None,
    upload_service: UploadServiceProtocol = Depends(get_upload_service),
    session: AsyncSession = Depends(access_scoped_session),
) -> UploadInitResponse:
    """Upload a document for ingestion.

    This endpoint:
    - Computes a stable `binary_hash` and checks duplicates (idempotent)
    - Stores the original file in S3, parses to Markdown, then enqueues processing

    Request format:
    - multipart/form-data with two parts:
      - `file`: the document (PDF, DOCX, etc.)
      - `hints` (optional): JSON part with Content-Type `application/json` matching `UploadHints`
        - Discriminator field: `strategy` → `finance_report` or `noop`

    Size limits:
    - Files larger than 50 MB are rejected with HTTP 413
    """

    # Basic content-type allowlist to prevent unexpected parsers from running
    allowed_types = {
        'application/pdf',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',  # .docx
        'application/msword',  # legacy .doc
        'text/plain',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',  # .xlsx (if you support it)
    }
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f'Unsupported content type: {file.content_type}',
        )

    # Enforce upload size guardrail (without consuming the stream)
    try:
        file.file.seek(0, 2)  # move to end
        size = file.file.tell()
        file.file.seek(0)  # rewind
    except Exception:
        size = None

    if size is not None and size > MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f'File is {size} bytes; limit is {MAX_UPLOAD_SIZE} bytes',
        )

    hints_model = parse_hints_from_any(hints)
    tmp_file = TemporaryUploadFile.from_upload(file)

    upload_input = StartUploadInput(
        file=tmp_file,
        hints=hints_model,
    )
    response = await upload_service.start_document_upload(session, payload=upload_input)

    job_kwargs = {
        **upload_input.model_dump(),
        'job_id': response.job_id,
        'document_id': response.document_id,
        'digest': response.digest,
        'access_context': AccessContext.from_session(session).model_dump(),
    }

    job_input = ContinueProcessingInput(**job_kwargs)

    background_tasks.add_task(upload_service.continue_processing, payload=job_input)
    return response
