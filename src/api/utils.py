from __future__ import annotations

from fastapi import HTTPException
from loguru import logger
from starlette import status

from core.config import get_settings


async def check_file_type_size(file):
    settings = get_settings()
    if file.content_type not in settings.allowed_upload_files.content_type:
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
    limit = settings.allowed_upload_files.upload_size_limit
    if size is not None and size > limit:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f'File is {size} bytes; limit is {limit} bytes',
        )
