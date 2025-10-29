from __future__ import annotations

from typing import AsyncIterator, Literal, Tuple
from uuid import UUID

from sqlmodel.ext.asyncio.session import AsyncSession

from profiles.registry import get_profile
from repositories import DocumentRepository, document_repository
from repositories.models import DocumentRecord
from repositories.schemas import DocumentCreate, DocumentUpdate
from schemas.documents import (
    DocumentListFilters,
    DocumentListResponse,
    DocumentResponse,
)
from store.protocols import StoreProtocol
from store.providers import default_store_provider
from store.schemas import FileInfo
from utils.types import SHA256B64


class DocumentService:
    def __init__(
        self,
        *,
        repo: DocumentRepository | None = None,
    ) -> None:
        self.repo = repo or document_repository

    async def ensure_canonical_document(self, session, *, data: DocumentCreate) -> Tuple[DocumentRecord, bool]:
        return await self.repo.get_or_create(session, data=data)

    def _get_store(self, collection: str) -> StoreProtocol:
        store = default_store_provider(collection=collection)
        assert isinstance(store, StoreProtocol)
        return store

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

        record = await self.repo.get(session, document_id=document_id)
        store = self._get_store(record.collection)

        original_uri = store.make_uri(original_key) if original_key else None
        markdown_uri = store.make_uri(markdown_key) if markdown_key else None

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
        self,
        session: AsyncSession,
        *,
        document_id: UUID,
        which: Literal['original', 'markdown'],
    ) -> tuple[AsyncIterator[bytes], FileInfo, str]:
        """Resolve a document artifact and return (async_bytes_iter, metadata, key)."""
        record = await self.repo.get(session, document_id=document_id)
        store = self._get_store(record.collection)
        info = await store.info(document_id=document_id, digest=record.digest, tenant_id=record.tenant_id)
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
        meta = await store.head(key)
        streamer = store.stream(key)
        return streamer, meta, key

    async def stream_markdown(self, session: AsyncSession, document_id: UUID):
        return await self.stream_file(session, document_id=document_id, which='markdown')

    async def stream_original(self, session: AsyncSession, document_id: UUID):
        return await self.stream_file(session, document_id=document_id, which='original')

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
        filters: DocumentListFilters,
    ) -> DocumentListResponse:
        collection = None
        if filters.profile_name:
            try:
                collection = get_profile(filters.profile_name).collection
            except KeyError:
                collection = None

        repo_filters = filters.to_repo_filters(collection=collection)
        docs = await self.repo.get_many(session, filters=repo_filters)
        return DocumentListResponse.model_validate(docs)

    async def delete(self, session: AsyncSession, *, document_id: UUID) -> None:
        record = await self.repo.get(session, document_id=document_id)
        store = self._get_store(record.collection)
        deleted = await store.delete(document_id=document_id, digest=record.digest, tenant_id=record.tenant_id)
        if not deleted:
            raise RuntimeError('Failed to delete stored artifacts for document')
        await self.repo.delete(session, document_id=document_id)
