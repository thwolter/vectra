from __future__ import annotations

from datetime import datetime, timezone

from loguru import logger
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.repositories.models import DocumentRecord

from app.core.config import get_settings
from uuid import UUID, uuid4

from app.repositories.schemas import DocumentCreate

settings = get_settings()


class Document:
    @staticmethod
    async def get(session: AsyncSession, *, id: UUID) -> DocumentRecord:
        rec = await session.get(DocumentRecord, id)
        if not rec:
            raise RuntimeError('Document row not found for given id')
        return rec

    @staticmethod
    async def create(session: AsyncSession, *, data: DocumentCreate) -> UUID:
        new_id = uuid4()
        rec = DocumentRecord(
            id=new_id,
            tenant_id=session.info.tenant_id,
            created_by=session.info.user_id,
            collection=data.collection,
            digest=data.digest,
            original_filename=data.original_filename,
            content_type=data.content_type,
            size_bytes=data.size_bytes,
            meta=(data.meta if data.meta is not None else None),
        )
        try:
            session.add(rec)
            await session.commit()
        except IntegrityError as e:
            await session.rollback()
            if existing_id := await Document.find(session, data):
                return existing_id
            raise Exception(
                f'IntegrityError but no existing row found for {data.collection}/{data.digest}: {e}'
            )
        except Exception as e:
            await session.rollback()
            raise Exception(
                f'Failed to create document {data.collection}/{data.digest}: {e}'
            )
        return new_id

    @staticmethod
    async def find(session: AsyncSession, data):
        result = await session.execute(
            select(DocumentRecord.id).where(
                DocumentRecord.tenant_id == session.info.tenant_id,
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
        try:
            rec = await session.get(DocumentRecord, id)
            if not rec:
                logger.error(f'Document id {id} not found for URI update')
                return
            # Always store the store identifier
            rec.store = settings.document_store
            if original_uri is not None:
                rec.original_uri = original_uri
            if markdown_uri is not None:
                rec.markdown_uri = markdown_uri
            rec.updated_at = datetime.now(timezone.utc)
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error(f'Failed to update URIs for id {id}: {e}')

    @staticmethod
    async def update_metadata(
        session: AsyncSession,
        *,
        id: UUID,
        metadata: dict,
        replace: bool = False,
    ) -> None:
        rec = await session.get(DocumentRecord, id)
        if not rec:
            raise Exception(f'Document id {id} not found')
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
