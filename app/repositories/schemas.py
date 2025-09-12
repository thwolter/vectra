from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, Field

from app.utils.types import SHA256B64

@dataclass
class DocumentCreate(frozen=True):
    """Schema for creating a canonical Document row.

    Encapsulates the inputs required to insert a document or return the
    existing canonical row keyed by (collection, digest).
    """

    collection: str
    digest: SHA256B64
    original_filename: str | None = None
    content_type: str | None = None
    size_bytes: int | None = None
    meta: dict | None = Field(default=None)
