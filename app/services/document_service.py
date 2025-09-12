from __future__ import annotations

from typing import Optional, Literal, AsyncIterator
from uuid import UUID

from app.schemas.documents import (
    DocumentRef,
    DocumentListResponse,
)


from app.schemas.enums import CollectionEnum
from app.repositories.schemas import DocumentCreate
from app.store.protocols import StoreProtocol
from app.store.providers import default_store_provider
from app.store.local_store import make_uri
from app.store.schemas import FileInfo
from app.repositories.documents import Document


class DocumentService:
    """Service for document orchestration and maintenance.

    Responsibilities:
    - Canonical Document lifecycle (creation, attribute updates)
    - Future: query/list/reparse/reembed/delete endpoints
    """

    def __init__(self, *, collection: CollectionEnum):
        self.collection = collection
        self.store: StoreProtocol = default_store_provider(self.collection)

    async def ensure_canonical_document(
        self,
        session,
        *,
        digest: str,
        original_filename: str | None,
        content_type: str | None,
        size_bytes: int | None,
    ) -> UUID:
        """Create (or fetch) the canonical Document row and return its UUID string.

        Implements first-seen-wins for original_filename via repository upsert.
        """

        document_id = await Document.create(
            session,
            data=DocumentCreate(
                collection=self.collection.value,
                digest=digest,
                original_filename=original_filename,
                content_type=content_type,
                size_bytes=size_bytes,
                meta=None,
            ),
        )
        return document_id

    async def update_document_uris(
        self,
        session,
        *,
        document_id: UUID,
        original_key: str | None = None,
        markdown_key: str | None = None,
    ) -> None:
        """Generate store-specific URIs and persist them on the canonical document.

        This keeps the repository limited to database updates while the service
        coordinates with the DocumentStore to build fully qualified URIs.
        """

        original_uri = make_uri(original_key) if original_key else None
        markdown_uri = make_uri(markdown_key) if markdown_key else None

        if not original_uri and not markdown_uri:
            return

        await Document.update_uris(
            session,
            id=document_id,
            original_uri=original_uri,
            markdown_uri=markdown_uri,
        )

    async def stream_file(
        self, document_id: UUID, which: Literal['original', 'markdown']
    ) -> tuple[AsyncIterator[bytes], FileInfo, str]:
        """Resolve a document artifact and return (async_bytes_iter, metadata, key)."""
        info = await self.store.info(document_id)
        files = info.files
        target = None
        if which == 'markdown':
            target = next((f for f in files if f.key.endswith('document.md')), None)
        elif which == 'original':
            target = next(
                (f for f in files if f.key.split('/')[-1].startswith('original')),
                None,
            )
        else:
            raise ValueError("which must be 'original' or 'markdown'")

        if not target:
            raise FileNotFoundError(
                f'{which} file not found for document {document_id}'
            )
        key = target.key
        meta = await self.store.head(key)
        streamer = self.store.stream(key)
        return streamer, meta, key

    async def stream_markdown(self, document_id: UUID):
        return await self.stream_file(document_id, 'markdown')

    async def stream_original(self, document_id: UUID):
        return await self.stream_file(document_id, 'original')

    # Placeholders for API wiring; implementations to be added in future changes
    async def get_document(self, document_id: UUID) -> DocumentRef:
        raise NotImplementedError

    async def list_documents(
        self,
        *,
        company_id: Optional[str] = None,
        doc_type: Optional[str] = None,
        reporting_year: Optional[int] = None,
        scope: Optional[str] = None,
        status: Optional[str] = None,
        q: Optional[str] = None,
        page_token: Optional[str] = None,
        page_size: int = 50,
    ) -> DocumentListResponse:
        raise NotImplementedError

    async def delete(self, document_id: UUID) -> None:
        raise NotImplementedError
