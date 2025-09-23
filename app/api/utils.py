from __future__ import annotations

import json

from fastapi import HTTPException
from loguru import logger
from pydantic import TypeAdapter, ValidationError
from starlette import status

from app.core.profiles import ProcessingProfileSettings
from app.metadata.schemas import NoopHints
from app.schemas.upload import UploadHints


def parse_hints_from_any(hints_raw: str | None) -> UploadHints:
    if hints_raw is None or hints_raw == '':
        return NoopHints()
    try:
        hints_dict = json.loads(hints_raw)
        upload_hints_adapter = TypeAdapter(UploadHints)
        return upload_hints_adapter.validate_python(hints_dict)
    except (ValueError, ValidationError) as e:
        raise HTTPException(status_code=422, detail=f'Invalid hints: {e}')


async def check_file_type_size(file, *, config: ProcessingProfileSettings):
    if file.content_type not in config.allowed_upload_types:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f'Unsupported content type: {file.content_type}',
        )
    # Enforce upload size guardrail (without consuming the stream)
    try:
        file.file.seek(0, 2)  # move to end
        size = file.file.tell()
        file.file.seek(0)  # rewind
    except Exception as e:
        logger.warning(f'Failed to get file size: {e}')
        size = None
    if size is not None and size > config.max_upload_size:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f'File is {size} bytes; limit is {config.max_upload_size} bytes',
        )
