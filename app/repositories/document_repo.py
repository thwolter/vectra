from __future__ import annotations

from datetime import datetime, timezone
from typing import Tuple
from uuid import UUID

from loguru import logger
from sqlalchemy.exc import IntegrityError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.schemas import AccessContext
from app.core.config import get_settings
from app.repositories.exceptions import RecordAlreadyExistsError
from app.utils.types import SHA256B64

from .exceptions import RecordNotFoundError
from .models import DocumentRecord
from .schemas import DocumentCreate, DocumentUpdate

settings = get_settings()


class DocumentRepository:
    @staticmethod
    async def create(session: AsyncSession, *, data: DocumentCreate) -> DocumentRecord:
        """Insert or update a canonical document. Returns the document id and a boolean (True if created)"""
        access_ctx = AccessContext.from_session(session)

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

    @staticmethod
    async def get_or_create(session: AsyncSession, *, data: DocumentCreate) -> Tuple[DocumentRecord, bool]:
        """Fetch a document by digest scoped to the current tenant. If not found, create it."""
        try:
            result = await DocumentRepository.get_for_digest(session, digest=data.digest, collection=data.collection)
            return result, False
        except RecordNotFoundError:
            record = await DocumentRepository.create(session, data=data)
            return record, True

    @staticmethod
    async def get(session: AsyncSession, *, document_id: UUID) -> DocumentRecord:
        rec: DocumentRecord | None = await session.get(DocumentRecord, document_id)
        if rec is None:
            raise RecordNotFoundError('Document row not found for given id')
        return rec

    @staticmethod
    async def get_for_digest(session: AsyncSession, *, digest: SHA256B64, collection: str) -> DocumentRecord:
        """Fetch a document by digest scoped to the current tenant."""
        statement = select(DocumentRecord).where(
            DocumentRecord.digest == digest,
            DocumentRecord.collection == collection,
        )
        result = await session.exec(statement)
        row = result.one_or_none()
        if row is None:
            raise RecordNotFoundError('Document row not found for given digest')
        return row

    @staticmethod
    async def update(session: AsyncSession, *, document: DocumentUpdate, replace_meta: bool = False) -> DocumentRecord:
        record = await DocumentRepository.get(session, document_id=document.id)

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
            await session.commit()
            await session.refresh(record)
        except Exception as e:
            await session.rollback()
            logger.error(f'Failed to update progress for document {document.id}: {e}')
        return record

    @staticmethod
    async def exists(session: AsyncSession, *, document_id: UUID) -> bool:
        """Alias for exist(); provided for ergonomic/consistency purposes."""
        rec: DocumentRecord | None = await session.get(DocumentRecord, document_id)
        return rec is not None

    @staticmethod
    async def get_many(session: AsyncSession, *, filters: dict) -> list[DocumentRecord]:
        raise NotImplementedError

    @staticmethod
    async def delete(session: AsyncSession, *, document_id: UUID) -> bool:
        try:
            record = await DocumentRepository.get(session, document_id=document_id)
            if record is None:
                return False
            await session.delete(record)
            await session.commit()
            return True
        except Exception as e:
            await session.rollback()
            logger.error(f'Failed to delete document id {document_id}: {e}')
            return False
