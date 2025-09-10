from __future__ import annotations
import json

from fastapi import HTTPException
from pydantic import TypeAdapter, ValidationError

from app.schemas.upload import UploadHints
from app.metadata.schemas import NoopHints

MAX_UPLOAD_SIZE = 50 * 1024 * 1024  # 50 MB
READ_CHUNK_SIZE = 1024 * 1024  # 1 MB


def parse_hints_from_any(hints_raw: str | None) -> UploadHints:
    if hints_raw is None or hints_raw == '':
        return NoopHints()
    try:
        hints_dict = json.loads(hints_raw)
        upload_hints_adapter = TypeAdapter(UploadHints)
        return upload_hints_adapter.validate_python(hints_dict)
    except (ValueError, ValidationError) as e:
        raise HTTPException(status_code=422, detail=f'Invalid hints: {e}')
