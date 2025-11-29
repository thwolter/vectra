from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Tuple
from uuid import UUID

from loguru import logger
from sqlalchemy.exc import IntegrityError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from core.db import ensure_access_context
from repositories.exceptions import RecordAlreadyExistsError
from utils.types import SHA256B64

from .exceptions import RecordNotFoundError
from .models import DocumentRecord
from .schemas import DocumentCreate, DocumentUpdate


class DocumentRepository:
    """Data access layer for canonical documents."""

    async def create(self, session: AsyncSession, *, data: DocumentCreate) -> DocumentRecord:
        """Insert or update a canonical document. Returns the document id and a boolean (True if created)"""
        access_ctx = await ensure_access_context(session)

        record = DocumentRecord(
            created_by=access_ctx.user_id,
            tenant_id=access_ctx.tenant_id,
            collection=data.collection,
            digest=data.digest,
            original_filename=data.original_filename,
            content_type=data.content_type,
            size_bytes=data.size_bytes,
            original_uri=None,
            markdown_uri=None,
            store=None,
            meta=data.meta,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        session.add(record)
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            raise RecordAlreadyExistsError('Document with same digest already exists')
        return record

    async def get_or_create(self, session: AsyncSession, *, data: DocumentCreate) -> Tuple[DocumentRecord, bool]:
        """Fetch a document by digest scoped to the current tenant. If not found, create it."""
        try:
            result = await self.get_for_digest(session, digest=data.digest, collection=data.collection)
            return result, False
        except RecordNotFoundError:
            record = await self.create(session, data=data)
            return record, True

    async def get(self, session: AsyncSession, *, document_id: UUID) -> DocumentRecord:
        await ensure_access_context(session, verify=False)
        rec: DocumentRecord | None = await session.get(DocumentRecord, document_id)
        if rec is None:
            raise RecordNotFoundError('Document row not found for given id')
        return rec

    async def get_for_digest(self, session: AsyncSession, *, digest: SHA256B64, collection: str) -> DocumentRecord:
        """Fetch a document by digest scoped to the current tenant."""
        access_ctx = await ensure_access_context(session, verify=False)
        statement = (
            select(DocumentRecord)
            .where(
                DocumentRecord.tenant_id == access_ctx.tenant_id,
                DocumentRecord.digest == digest,
                DocumentRecord.collection == collection,
            )
            .limit(1)
        )
        result = await session.exec(statement)
        row = result.one_or_none()
        if row is None:
            raise RecordNotFoundError('Document row not found for given digest')
        return row

    async def update(
        self,
        session: AsyncSession,
        *,
        document: DocumentUpdate,
        replace_meta: bool = False,
    ) -> DocumentRecord:
        record = await self.get(session, document_id=document.id)

        if document.meta:
            if replace_meta:
                record.meta = dict(document.meta)
            else:
                base_meta = record.meta
                record.meta = {**base_meta, **document.meta}

        updates = document.model_dump(exclude_unset=True, exclude={'id'}, mode='json')
        for k, v in updates.items():
            setattr(record, k, v)

        try:
            await session.flush()
            await session.refresh(record)
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error(f'Failed to update progress for document {document.id}: {e}')
        return record

    async def exists(self, session: AsyncSession, *, document_id: UUID) -> bool:
        """Alias for exist(); provided for ergonomic/consistency purposes."""
        await ensure_access_context(session, verify=False)
        rec: DocumentRecord | None = await session.get(DocumentRecord, document_id)
        return rec is not None

    async def get_many(self, session: AsyncSession, *, filters: dict) -> dict[str, Any]:
        access_ctx = await ensure_access_context(session, verify=False)
        offset = int(filters.get('offset', 0) or 0)
        limit = int(filters.get('limit', 20) or 20)
        query = filters.get('query')
        collection = filters.get('collection')
        columns = DocumentRecord.__table__.columns  # type: ignore[missing-attribute]

        stmt = (
            select(DocumentRecord)
            .where(DocumentRecord.tenant_id == access_ctx.tenant_id)
            .order_by(columns.created_at.desc())
        )

        if collection:
            stmt = stmt.where(DocumentRecord.collection == collection)

        if query:
            stmt = stmt.where(columns.original_filename.ilike(f'%{query}%'))

        result = await session.exec(stmt.offset(offset).limit(limit + 1))
        rows = result.all()
        has_more = len(rows) > limit
        items = rows[:limit]
        next_token = str(offset + limit) if has_more else None

        return {
            'items': items,
            'next_page_token': next_token,
        }

    async def delete(self, session: AsyncSession, *, document_id: UUID) -> bool:
        try:
            record = await self.get(session, document_id=document_id)
            if record is None:
                return False
            await session.delete(record)
            await session.commit()
            return True
        except Exception as e:
            await session.rollback()
            logger.error(f'Failed to delete document id {document_id}: {e}')
            return False


document_repository = DocumentRepository()
