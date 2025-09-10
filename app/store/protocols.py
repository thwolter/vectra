from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable, AsyncIterator
from uuid import UUID

from app.api.file import TemporaryUploadFile
from app.schemas.enums import CollectionEnum
from app.store.schemas import ArtifactInfo, FileInfo, StoredFiles


@runtime_checkable
class StoreProtocol(Protocol):
    def __init__(
        self, collection: CollectionEnum, *, base_path: str | Path | None = None
    ) -> None: ...

    async def save_original(
        self,
        file: TemporaryUploadFile,
        *,
        document_id: UUID,
        compress: bool | None = None,
    ) -> ArtifactInfo: ...

    async def save_markdown(
        self,
        md_text: str,
        *,
        document_id: UUID,
    ) -> ArtifactInfo: ...

    async def delete(
        self,
        document_id: UUID,
        *,
        delete_original: bool = True,
        delete_markdown: bool = True,
    ) -> bool: ...

    def stream(self, key: str, *, chunk_size: int = 65536) -> AsyncIterator[bytes]: ...

    async def head(self, key: str) -> FileInfo: ...

    async def info(self, document_id: UUID) -> StoredFiles: ...
