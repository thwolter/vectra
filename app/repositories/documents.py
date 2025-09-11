from __future__ import annotations

from typing import Any
from datetime import datetime, timezone

from loguru import logger
from sqlalchemy import text, bindparam
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import JSONB

from app.repositories.models import Document

from app.core.config import get_settings
from uuid import UUID, uuid4

from app.repositories.schemas import DocumentCreate
from app.repositories.mixins import EnsureTableMixin

settings = get_settings()


class DocumentRepository(EnsureTableMixin):
    async def get(self, session: AsyncSession, *, id: UUID) -> Document:
        await self._ensure_schema_once()
        sql = (
            'SELECT id, tenant_id, collection, digest, original_filename, content_type, size_bytes, original_uri, '
            'markdown_uri, store, meta, created_at, COALESCE(updated_at, created_at) AS updated_at, created_by '
            'FROM documents WHERE id = :id LIMIT 1'
        )
        res = await session.execute(text(sql), params={'id': id})
        row = res.mappings().first()
        if not row:
            raise RuntimeError('Document row not found for given id')
        return Document(**dict(row))

    async def create(self, session: AsyncSession, *, data: DocumentCreate) -> UUID:
        await self._ensure_schema_once()

        sql = (
            'INSERT INTO documents ('
            ' id, tenant_id, created_by, collection, digest, original_filename, content_type, '
            ' size_bytes, meta, created_at, updated_at) '
            ' VALUES ('
            " :id, current_setting('app.tenant_id', true)::uuid, :created_by, :collection, :digest, "
            " :original_filename, :content_type, :size_bytes, :meta, timezone('utc', now()), timezone('utc', now())) "
            ' ON CONFLICT (tenant_id, collection, digest) DO UPDATE SET id = documents.id'
            ' RETURNING id'
        )
        params = {
            'id': uuid4(),
            'created_by': session.info.user_id,
            'collection': data.collection,
            'digest': data.digest,
            'original_filename': data.original_filename,
            'content_type': data.content_type,
            'size_bytes': data.size_bytes,
            'meta': (data.meta if data.meta is not None else None),
        }
        try:
            stmt = text(sql).bindparams(bindparam('meta', type_=JSONB))
            res = await session.execute(stmt, params)
            row = res.fetchone()
            await session.commit()
        except Exception as e:
            await session.rollback()
            raise Exception(
                f'Failed to create document {data.collection}/{data.digest}: {e}'
            )
        if not row:
            raise RuntimeError('Insert into documents did not return an id')
        return row[0]

    async def update_uris_by_id(
        self,
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
        await self._ensure_schema_once()
        sets = []
        params: dict[str, Any] = {
            'id': id,
            'store': settings.document_store,
            'updated_at': datetime.now(timezone.utc),
        }
        # Always store the store identifier
        sets.append('store = :store')
        if original_uri:
            sets.append('original_uri = :original_uri')
            params['original_uri'] = original_uri
        if markdown_uri:
            sets.append('markdown_uri = :markdown_uri')
            params['markdown_uri'] = markdown_uri
        # Always bump updated_at on any change
        sets.append('updated_at = :updated_at')
        sql = 'UPDATE documents SET ' + ', '.join(sets) + ' WHERE id = :id'
        try:
            await session.execute(text(sql), params)
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error(f'Failed to update URIs for id {id}: {e}')

    async def update_metadata(
        self,
        session: AsyncSession,
        *,
        id: UUID,
        metadata: dict,
        replace: bool = False,
    ) -> None:
        """Update the meta JSONB field for a canonical document identified by primary key id."""
        await self._ensure_schema_once()
        if replace:
            sql = 'UPDATE documents SET meta = :meta, updated_at = :updated_at WHERE id = :id'
            meta_payload = metadata
        else:
            sql = (
                "UPDATE documents SET meta = COALESCE(meta, '{}'::JSONB) || :meta, "
                'updated_at = :updated_at WHERE id = :id'
            )
            meta_payload = metadata or {}
        params: dict[str, Any] = {
            'id': id,
            'meta': meta_payload,
            'updated_at': datetime.now(timezone.utc),
        }
        try:
            stmt = text(sql).bindparams(bindparam('meta', type_=JSONB))
            await session.execute(stmt, params)
            await session.commit()
        except Exception as e:
            await session.rollback()
            raise Exception(f'Failed to update metadata for id {id}: {e}')

    async def delete(self, session: AsyncSession, *, id: UUID) -> bool:
        """Delete a canonical document by primary key.

        Uses DELETE ... RETURNING to determine if a row was removed.

        Returns:
            True if a row was deleted; False if no matching row existed.
        """
        await self._ensure_schema_once()
        sql = 'DELETE FROM documents WHERE id = :id RETURNING id'
        try:
            res = await session.execute(text(sql), {'id': id})
            row = res.fetchone()
            await session.commit()
            return bool(row)
        except Exception as e:
            await session.rollback()
            logger.error(f'Failed to delete document id {id}: {e}')
            return False
