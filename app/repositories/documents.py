from __future__ import annotations

from datetime import datetime, timezone
from typing import Tuple

from loguru import logger
from sqlalchemy import literal_column
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.repositories.models import DocumentRecord

from app.core.config import get_settings
from uuid import UUID, uuid4

from app.repositories.schemas import DocumentCreate
from .exceptions import DocumentNotFoundError, DocumentUpdateError
from sqlalchemy.dialects.postgresql import insert

settings = get_settings()


class Document:
    @staticmethod
    async def get(session: AsyncSession, *, id: UUID) -> DocumentRecord:
        rec: DocumentRecord | None = await session.get(DocumentRecord, id)
        if rec is None:
            raise DocumentNotFoundError('Document row not found for given id')
        return rec

    @staticmethod
    async def upsert(
        session: AsyncSession, *, data: DocumentCreate
    ) -> Tuple[UUID, bool]:
        """Insert or update a canonical document. Returns the document id and a boolean (True if created)"""
        tenant_id = session.info['tenant_id']
        user_id = session.info['user_id']

        raw_meta = getattr(data, 'meta', None)
        meta_ = None if raw_meta in (None, 'null') else raw_meta

        stmt = (
            insert(DocumentRecord)
            .values(
                id=uuid4(),
                tenant_id=tenant_id,
                created_by=user_id,
                collection=data.collection,
                digest=data.digest,
                original_filename=data.original_filename,
                content_type=data.content_type,
                size_bytes=data.size_bytes,
                original_uri=None,
                markdown_uri=None,
                store=None,
                meta=meta_,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            .on_conflict_do_update(
                index_elements=[
                    DocumentRecord.tenant_id,
                    DocumentRecord.collection,
                    DocumentRecord.digest,
                ],
                # true no-op update; enables RETURNING on conflict
                set_={'id': DocumentRecord.id},
            )
            .returning(
                DocumentRecord.id,
                # inserted=True iff it was an INSERT (xmax==0)
                literal_column('(xmax = 0)').label('inserted'),
            )
        )

        res = await session.execute(stmt)
        row = res.one()  # (id, inserted)
        await session.commit()

        doc_id = row[0]
        created = bool(row[1])
        return doc_id, created

    @staticmethod
    async def find(session: AsyncSession, data):
        result = await session.execute(
            select(DocumentRecord.id).where(
                DocumentRecord.tenant_id == session.info['tenant_id'],
                DocumentRecord.collection == data.collection,
                DocumentRecord.digest == data.digest,
            )
        )
        existing_id = result.scalar_one_or_none()
        return existing_id

    @staticmethod
    async def update_uris(
        session: AsyncSession,
        *,
        id: UUID,
        original_uri: str | None = None,
        markdown_uri: str | None = None,
    ) -> None:
        """Update URI fields for a canonical document by primary key id.

        Expects fully-qualified URIs to be provided by the caller (service layer).
        Does not modify original_filename. Also persists the backing store name.
        """
        rec = await Document.get(session, id=id)
        rec.store = settings.document_store
        if original_uri is not None:
            rec.original_uri = original_uri
        if markdown_uri is not None:
            rec.markdown_uri = markdown_uri
        rec.updated_at = datetime.now(timezone.utc)
        try:
            await session.commit()
        except Exception as e:
            await session.rollback()
            raise DocumentUpdateError(f'Failed to update URIs for id {id}: {e}')

    @staticmethod
    async def update_metadata(
        session: AsyncSession,
        *,
        id: UUID,
        metadata: dict,
        replace: bool = False,
    ) -> None:
        rec = await Document.get(session, id=id)
        if replace:
            rec.meta = metadata
        else:
            base_meta = rec.meta or {}
            rec.meta = {**base_meta, **metadata}
            rec.updated_at = datetime.now(timezone.utc)
            assert type(rec.meta) is dict, 'metadata must be a dict'
        try:
            await session.commit()
        except Exception as e:
            await session.rollback()
            raise Exception(f'Failed to update metadata for id {id}: {e}')

    @staticmethod
    async def delete(session: AsyncSession, *, id: UUID) -> bool:
        """Delete a canonical document by primary key.

        Uses ORM delete to remove the row.

        Returns:
            True if a row was deleted; False if no matching row existed.
        """
        try:
            rec = await session.get(DocumentRecord, id)
            if not rec:
                return False
            await session.delete(rec)
            await session.commit()
            return True
        except Exception as e:
            await session.rollback()
            logger.error(f'Failed to delete document id {id}: {e}')
            return False
