from typing import Any, overload

from langchain_core.documents import Document
from loguru import logger
from sqlalchemy import text
from sqlmodel.ext.asyncio.session import AsyncSession

from core.config import get_settings
from utils.types import SHA256B64

APP_SCHEMA = get_settings().db_schema

_LC_COLLECTION = f'{APP_SCHEMA}.langchain_pg_collection'
_LC_EMBEDDING = f'{APP_SCHEMA}.langchain_pg_embedding'


class EmbeddingsRepository:
    _ALLOWED_FILTERS = {
        'digest': "e.cmetadata->>'digest'",
        'source': "e.cmetadata->>'source'",
    }

    @overload
    async def exists(self, session: AsyncSession, *, collection: str, digest: str) -> bool: ...

    @overload
    async def exists(self, session: AsyncSession, *, collection: str, source: str) -> bool: ...

    @overload
    async def exists(self, session: AsyncSession, *, collection: str, digest: str, source: str) -> bool: ...

    async def exists(self, session: AsyncSession, *, collection: str, **filters: Any) -> bool:
        if not filters:
            raise ValueError('Provide at least one filter (digest=..., source=...).')

        unknown = set(filters) - set(self._ALLOWED_FILTERS)
        if unknown:
            raise ValueError(f'Unsupported filters: {", ".join(sorted(unknown))}')

        where = ' AND '.join(f'{self._ALLOWED_FILTERS[k]} = :{k}' for k in filters)
        sql = f"""
                SELECT EXISTS (
                    SELECT 1
                    FROM {_LC_EMBEDDING} e
                    JOIN {_LC_COLLECTION} c ON e.collection_id = c.uuid
                    WHERE c.name = :collection AND {where}
                )
            """
        params = {'collection': collection, **filters}
        stmt: Any = text(sql)
        result = await session.exec(stmt, params=params)  # type: ignore[arg-type]
        return bool(result.scalar())

    async def fetch_documents(self, session: AsyncSession, *, collection: str, digest: str) -> list[Document]:
        """Return stored documents for a given collection + digest from PGVector metadata."""
        sql = f"""
            SELECT e.document, e.cmetadata
            FROM {_LC_EMBEDDING} e
            JOIN {_LC_COLLECTION} c ON e.collection_id = c.uuid
            WHERE c.name = :collection AND e.cmetadata->>'digest' = :digest
            ORDER BY COALESCE((e.cmetadata->>'chunk_id')::int, 0)
        """
        params = {'collection': collection, 'digest': digest}
        stmt: Any = text(sql)
        result = await session.exec(stmt, params=params)  # type: ignore[arg-type]
        rows = result.all()

        documents: list[Document] = []
        for row in rows:
            mapping = row._mapping if hasattr(row, '_mapping') else {'document': row[0], 'cmetadata': row[1]}
            content = mapping.get('document') or ''
            metadata = mapping.get('cmetadata') or {}
            meta_dict = dict(metadata)
            documents.append(Document(page_content=content, metadata=meta_dict))
        return documents

    async def delete(self, session: AsyncSession, *, digest: SHA256B64) -> None:
        """Delete all embeddings for a given logical document id (metadata.digest)."""
        if not digest:
            raise ValueError('digest must be a non-empty string')

        logger.info(f"Deleting embeddings with digest='{digest}'")

        delete_sql = f"DELETE FROM {_LC_EMBEDDING} WHERE cmetadata->>'digest' = :digest"

        stmt: Any = text(delete_sql)
        await session.exec(stmt, params={'digest': digest})  # type: ignore[arg-type]
        await session.commit()

        logger.success(f"Deleted embeddings for digest='{digest}'")

    async def update_source(
        self,
        session: AsyncSession,
        *,
        collection: str,
        digest: str,
        source: str,
    ) -> int:
        """Update the `source` field in embedding metadata for the given collection + digest."""
        if not source:
            raise ValueError('source must be a non-empty string')

        sql = f"""
            UPDATE {_LC_EMBEDDING} e
            SET cmetadata = jsonb_set(
                e.cmetadata,
                '{{source}}',
                to_jsonb(CAST(:source AS text)),
                true
            )
            FROM {_LC_COLLECTION} c
            WHERE e.collection_id = c.uuid
              AND c.name = :collection
              AND e.cmetadata->>'digest' = :digest
        """
        params = {'collection': collection, 'digest': digest, 'source': source}
        stmt: Any = text(sql)
        result = await session.exec(stmt, params=params)  # type: ignore[arg-type]
        await session.commit()
        rowcount = result.rowcount if result is not None else 0
        logger.info(
            "Updated embedding sources for collection='{collection}' digest='{digest}' (rows={rows})",
            collection=collection,
            digest=digest,
            rows=rowcount,
        )
        return rowcount


embeddings_repository = EmbeddingsRepository()
