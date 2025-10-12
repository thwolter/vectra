from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, UploadFile
from sqlmodel.ext.asyncio.session import AsyncSession
from tenauth.schemas import AccessContext

from app.core.dependencies import (
    access_scoped_session,
    require_access_context,
    require_auth,
)
from app.profiles.registry import ProcessingProfileSettings
from app.protocols.services import UploadServiceProtocol
from app.schemas.upload import (
    ContinueProcessingInput,
    StartUploadInput,
    UploadInitResponse,
)
from app.services.factory import get_profile_settings, get_upload_service
from app.worker.dispatcher import enqueue_upload_processing

from ..file import TemporaryUploadFile
from ..utils import check_file_type_size

router = APIRouter(
    prefix='/v1',
    dependencies=[Depends(require_auth), Depends(require_access_context)],
)


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
    file: Annotated[UploadFile, File(description='Document to upload (PDF, DOCX, etc.)')],
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

    Size limits:
    - Files larger than 50 MB are rejected with HTTP 413
    - Optional `hints` form field is accepted for backwards compatibility but ignored
    """

    await check_file_type_size(file, config=config)

    tmp_file = TemporaryUploadFile.from_upload(file)

    upload_input = StartUploadInput(file=tmp_file)
    response = await upload_service.initiate_document_intake(session, payload=upload_input)

    job_kwargs = {
        'file': upload_input.file,
        'job_id': response.job_id,
        'document_id': response.document_id,
        'digest': response.digest,
        'access_context': AccessContext.from_session(session),
    }

    job_input = ContinueProcessingInput(**job_kwargs)

    await enqueue_upload_processing(job_input)
    return response
