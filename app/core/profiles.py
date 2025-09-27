from __future__ import annotations

from pydantic import BaseModel

from app.metadata.config import ExtractConfig
from app.parsers.docling import DoclingParserConfig
from app.parsers.schemas import ParserConfig
from app.vector.models import IngestorSettings


class ProcessingProfileSettings(BaseModel):
    name: str = 'default'
    collection: str = 'default'

    max_upload_size: int = 50 * 1024 * 1024  # 50 MB
    allowed_upload_types: set[str] = {
        'application/pdf',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',  # .docx
        'application/msword',  # legacy .doc
        'text/plain',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',  # .xlsx (if you support it)
    }

    ingestor_config: IngestorSettings = IngestorSettings()

    parser: str = 'docling'
    parser_config: ParserConfig = DoclingParserConfig()

    extract_config: ExtractConfig = ExtractConfig()
