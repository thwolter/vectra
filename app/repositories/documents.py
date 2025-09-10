from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
import json

from loguru import logger
from sqlalchemy import text, bindparam
from sqlalchemy.dialects.postgresql import JSONB

from app.repositories.models import Document

from app.core.config import get_settings
from uuid import uuid4, UUID

from app.repositories.schemas import DocumentCreate

settings = get_settings()


class DocumentRepository:
    """Repository for canonical documents (collection + binary_hash).

    Responsibilities:
    - Ensure documents table exists
    - First-seen wins for original_filename (immutable)
    - Update S3 URIs and basic attributes
    """

    def __init__(self, db_manager: Any):
        self.db_manager = db_manager

    async def _ensure_db(self) -> None:
        if not self.db_manager.is_initialized:
            await self.db_manager.initialize()

    async def ensure_documents_table(self) -> None:
        await self._ensure_db()
        await self.db_manager.ensure_schema()

    async def get(self, *, id: UUID) -> Document:
        """Fetch a document row by UUID and return a Document model instance."""
        await self.ensure_documents_table()
        async with self.db_manager.get_session() as session:
            select_sql = (
                'SELECT id, collection, digest, original_filename, content_type, size_bytes, original_uri, markdown_uri, meta, created_at '
                'FROM documents WHERE id = :id LIMIT 1'
            )
            res = await session.execute(text(select_sql), {'id': id})
            row = res.fetchone()
            if not row:
                raise RuntimeError('Document row not found for given id')
            return Document(
                id=row[0],
                collection=row[1],
                digest=row[2],
                original_filename=row[3],
                content_type=row[4],
                size_bytes=row[5],
                original_uri=row[6],
                markdown_uri=row[7],
                meta=row[8],
                created_at=row[9],
            )

    async def create(self, data: DocumentCreate) -> UUID:
        """Insert row if not exists and return the canonical id (UUID as str).

        Enforces first-seen immutable original_filename by using ON CONFLICT DO NOTHING.
        """
        await self.ensure_documents_table()
        async with self.db_manager.get_session() as session:
            now = datetime.now(timezone.utc)
            new_id = uuid4()
            insert_sql = (
                'INSERT INTO documents (id, collection, digest, original_filename, content_type, size_bytes, meta, created_at) '
                'VALUES (:id, :collection, :digest, :original_filename, :content_type, :size_bytes, CAST(:meta AS JSONB), :created_at) '
                'ON CONFLICT (collection, digest) DO NOTHING'
            )
            params = {
                'id': new_id,
                'collection': data.collection,
                'digest': data.digest,
                'original_filename': data.original_filename,
                'content_type': data.content_type,
                'size_bytes': data.size_bytes,
                'meta': json.dumps(data.meta) if data.meta is not None else None,
                'created_at': now,
            }
            try:
                await session.execute(text(insert_sql), params)
                await session.commit()
            except Exception as e:
                await session.rollback()
                logger.error(
                    f'Failed to insert document {data.collection}/{data.digest}: {e}'
                )
            # Select row to get id in either case (inserted or existing)
            select_sql = 'SELECT id FROM documents WHERE collection = :collection AND digest = :digest LIMIT 1'
            res = await session.execute(
                text(select_sql), {'collection': data.collection, 'digest': data.digest}
            )
            row = res.fetchone()
            if not row:
                raise RuntimeError('Document row not found after insert/select')
            return row[0]

    async def update_uris_by_id(
        self,
        *,
        id: UUID,
        original_uri: str | None = None,
        markdown_uri: str | None = None,
    ) -> None:
        """Update URI fields for a canonical document by primary key id.

        Expects fully-qualified URIs to be provided by the caller (service layer).
        Does not modify original_filename. Also persists the backing store name.
        """
        await self.ensure_documents_table()
        sets = []
        params: dict[str, Any] = {
            'id': id,
            'store': settings.document_store,
        }
        # Always store the store identifier
        sets.append('store = :store')
        if original_uri:
            sets.append('original_uri = :original_uri')
            params['original_uri'] = original_uri
        if markdown_uri:
            sets.append('markdown_uri = :markdown_uri')
            params['markdown_uri'] = markdown_uri
        sql = 'UPDATE documents SET ' + ', '.join(sets) + ' WHERE id = :id'
        async with self.db_manager.get_session() as session:
            try:
                await session.execute(text(sql), params)
                await session.commit()
            except Exception as e:
                await session.rollback()
                logger.error(f'Failed to update URIs for id {id}: {e}')

    async def update_metadata(
        self,
        *,
        id: UUID,
        metadata: dict,
        replace: bool = False,
    ) -> None:
        """Update the meta JSONB field for a canonical document identified by primary key id.

        Args:
            id: Document primary key.
            metadata: Partial or full metadata to apply.
            replace: If True, replace entirely. If False (default), merge keys into existing meta (shallow).
        """
        await self.ensure_documents_table()
        if replace:
            sql = 'UPDATE documents SET meta = :meta WHERE id = :id'
            meta_payload = metadata
        else:
            sql = (
                "UPDATE documents SET meta = COALESCE(meta, '{}'::JSONB) || :meta "
                'WHERE id = :id'
            )
            meta_payload = metadata or {}
        params: dict[str, Any] = {
            'id': id,
            'meta': meta_payload,
        }
        async with self.db_manager.get_session() as session:
            try:
                stmt = text(sql).bindparams(bindparam('meta', type_=JSONB))
                await session.execute(stmt, params)
                await session.commit()
            except Exception as e:
                await session.rollback()
                raise Exception(f'Failed to update metadata for id {id}: {e}')

    async def delete(self, *, id: UUID) -> bool:
        """Delete a canonical document by primary key.

        Uses DELETE ... RETURNING to determine if a row was removed.

        Returns:
            True if a row was deleted; False if no matching row existed.
        """
        await self.ensure_documents_table()
        sql = 'DELETE FROM documents WHERE id = :id RETURNING id'
        async with self.db_manager.get_session() as session:
            try:
                res = await session.execute(text(sql), {'id': id})
                row = res.fetchone()
                await session.commit()
                return bool(row)
            except Exception as e:
                await session.rollback()
                logger.error(f'Failed to delete document id {id}: {e}')
                return False
