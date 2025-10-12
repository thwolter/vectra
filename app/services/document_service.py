from __future__ import annotations

from typing import AsyncIterator, Literal, Tuple
from uuid import UUID

from sqlmodel.ext.asyncio.session import AsyncSession

from app.repositories import DocumentRepository, document_repository
from app.repositories.models import DocumentRecord
from app.repositories.schemas import DocumentCreate, DocumentUpdate
from app.schemas.documents import DocumentListResponse, DocumentResponse
from app.store.local_store import make_uri
from app.store.protocols import StoreProtocol
from app.store.providers import default_store_provider
from app.store.schemas import FileInfo
from app.utils.types import SHA256B64


class DocumentService:
    def __init__(
        self,
        *,
        repo: DocumentRepository | None = None,
    ) -> None:
        self.store = default_store_provider('default')
        assert isinstance(self.store, StoreProtocol)
        self.repo = repo or document_repository

    async def ensure_canonical_document(self, session, *, data: DocumentCreate) -> Tuple[DocumentRecord, bool]:
        return await self.repo.get_or_create(session, data=data)

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

        await self.repo.update(
            session,
            document=DocumentUpdate(
                id=document_id,
                original_uri=original_uri,
                markdown_uri=markdown_uri,
            ),
        )

    async def stream_file(
        self, document_id: UUID, which: Literal['original', 'markdown']
    ) -> tuple[AsyncIterator[bytes], FileInfo, str]:
        """Resolve a document artifact and return (async_bytes_iter, metadata, key)."""
        info = await self.store.info(document_id)
        files = info.files
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
            raise FileNotFoundError(f'{which} file not found for document {document_id}')
        key = target.key
        meta = await self.store.head(key)
        streamer = self.store.stream(key)
        return streamer, meta, key

    async def stream_markdown(self, document_id: UUID):
        return await self.stream_file(document_id, 'markdown')

    async def stream_original(self, document_id: UUID):
        return await self.stream_file(document_id, 'original')

    async def get_document(self, session: AsyncSession, *, document_id: UUID) -> DocumentResponse:
        doc = await self.repo.get(session, document_id=document_id)
        return DocumentResponse.model_validate(doc)

    async def get_document_by_digest(
        self, session: AsyncSession, *, digest: SHA256B64, collection: str
    ) -> DocumentResponse:
        doc = await self.repo.get_for_digest(session, digest=digest, collection=collection)
        return DocumentResponse.model_validate(doc)

    async def list_documents(
        self,
        session: AsyncSession,
        *,
        filters: dict,
    ) -> DocumentListResponse:
        docs = self.repo.get_many(session, filters=filters)
        return DocumentListResponse.model_validate(docs)

    async def delete(self, session: AsyncSession, *, document_id: UUID) -> None:
        await self.repo.delete(session, document_id=document_id)
