from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List
from uuid import UUID

from pydantic import BaseModel

from app.schemas.enums import CollectionEnum


@dataclass(frozen=True)
class ArtifactInfo:
    """Lightweight result for store write operations.

    Attributes:
        document_id: Canonical identifier for the document; may be a UUID or a precomputed hash.
        collection: Logical collection scope for the document.
        original_key: Store key/URI to the original file if saved; otherwise None.
        markdown_key: Store key/URI to the markdown copy if saved; otherwise None.
    """

    document_id: UUID
    collection: CollectionEnum
    original_key: str | None
    markdown_key: str | None


class FileInfo(BaseModel):
    key: str
    size: int
    last_modified: str
    content_type: str
    content_encoding: str | None = None
    metadata: dict[str, Any]


class StoredFiles(BaseModel):
    document_id: UUID
    collection: str
    files: List[FileInfo]
