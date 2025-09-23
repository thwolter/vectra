from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, UploadFile
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.dependencies import access_scoped_session
from app.core.profiles import ProcessingProfileSettings
from app.protocols.services import UploadServiceProtocol
from app.schemas.upload import (
    ContinueProcessingInput,
    StartUploadInput,
    UploadInitResponse,
)
from app.services.dependencies import get_profile_settings, get_upload_service

from ..file import TemporaryUploadFile
from ..schemas import AccessContext
from ..utils import check_file_type_size, parse_hints_from_any

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
    file: Annotated[UploadFile, File(description='Document to upload (PDF, DOCX, etc.)')],
    hints: Annotated[str | None, Form(description='Optional hints for document parsing')] = None,
    upload_service: UploadServiceProtocol = Depends(get_upload_service),
    config: ProcessingProfileSettings = Depends(get_profile_settings),
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

    await check_file_type_size(file, config=config)

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
