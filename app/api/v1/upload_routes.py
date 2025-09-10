from __future__ import annotations

from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    UploadFile,
    BackgroundTasks,
    Form,
)

from app.api.file import TemporaryUploadFile
from app.api.utils import parse_hints_from_any
from app.protocols.services import UploadServiceProtocol
from app.services.factory import get_upload_service
from app.schemas.upload import (
    UploadInitResponse,
    StartUploadInput,
    ContinueProcessingInput,
)

# Hard limits to protect memory/CPU. Adjust via settings if needed.
MAX_UPLOAD_SIZE = 50 * 1024 * 1024  # 50 MB
READ_CHUNK_SIZE = 1024 * 1024  # 1 MB

router = APIRouter(prefix='/v1')


@router.post('/uploads', response_model=UploadInitResponse, tags=['uploads'])
async def upload_document(
    background_tasks: BackgroundTasks,
    file: Annotated[
        UploadFile, File(description='Document to upload (PDF, DOCX, etc.)')
    ],
    hints: Annotated[
        str | None, Form(description='Optional hints for document parsing')
    ] = None,
    upload_service: UploadServiceProtocol = Depends(get_upload_service),
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

    hints_model = parse_hints_from_any(hints)
    tmp_file = TemporaryUploadFile.from_upload(file)

    upload_input = StartUploadInput(
        file=tmp_file,
        hints=hints_model,
    )
    response = await upload_service.start_document_upload(upload_input)

    job_input = ContinueProcessingInput(
        **upload_input.model_dump(),
        job_id=response.job_id,
        document_id=response.document_id,
        digest=response.digest,
    )

    background_tasks.add_task(upload_service.continue_processing, job_input)
    return response
