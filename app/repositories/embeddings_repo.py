"""
Repositories for metadata-related data access.

Contains MetadataRepository responsible for metadata queries and updates.
"""

import json
from typing import Any, Dict, List, overload

from loguru import logger
from sqlalchemy import text
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app.utils.types import SHA256B64

_metadata = SQLModel.metadata


class EmbeddingsRepository:
    _ALLOWED_FILTERS = {
        'digest': "e.cmetadata->>'digest'",
        'source': "e.cmetadata->>'source'",
    }

    @staticmethod
    async def update_metadata(
        session: AsyncSession,
        *,
        digest: SHA256B64,
        metadata: Dict[str, Any],
        collection: str,
        replace: bool = False,
    ) -> None:
        if not metadata:
            return

        if replace:
            # Replace while preserving the digest needed for future lookups
            set_clause = "cmetadata = jsonb_build_object('digest', e.cmetadata->>'digest') || CAST(:metadata AS JSONB)"
        else:
            set_clause = "cmetadata = COALESCE(e.cmetadata, '{}'::JSONB) || CAST(:metadata AS JSONB)"

        sql = (
            'UPDATE langchain_pg_embedding e '
            f'SET {set_clause} '
            'FROM langchain_pg_collection c '
            'WHERE e.collection_id = c.uuid AND c.name = :collection '
            "AND e.cmetadata->>'digest' = :digest"
        )
        # Serialize metadata to JSON string for consistent parameter handling across drivers
        metadata_json = json.dumps(metadata)
        params = {
            'collection': collection,
            'metadata': metadata_json,
            'digest': digest,
        }
        # Rely on explicit CAST(:metadata AS JSONB) in SQL; no need for JSONB bind param
        stmt: Any = text(sql)

        try:
            await session.exec(stmt, params=params)  # type: ignore[arg-type]
            await session.commit()
        except Exception as e:
            logger.error(f"Failed to update metadata for digest '{digest}': {e}")

    @overload
    @staticmethod
    async def exists(session: AsyncSession, *, collection: str, digest: str) -> bool: ...

    @overload
    @staticmethod
    async def exists(session: AsyncSession, *, collection: str, source: str) -> bool: ...

    @overload
    @staticmethod
    async def exists(session: AsyncSession, *, collection: str, digest: str, source: str) -> bool: ...

    @staticmethod
    async def exists(session: AsyncSession, *, collection: str, **filters: Any) -> bool:
        if not filters:
            raise ValueError('Provide at least one filter (digest=..., source=...).')

        unknown = set(filters) - set(EmbeddingsRepository._ALLOWED_FILTERS)
        if unknown:
            raise ValueError(f'Unsupported filters: {", ".join(sorted(unknown))}')

        where = ' AND '.join(f'{EmbeddingsRepository._ALLOWED_FILTERS[k]} = :{k}' for k in filters)
        sql = f"""
                SELECT EXISTS (
                    SELECT 1
                    FROM langchain_pg_embedding e
                    JOIN langchain_pg_collection c ON e.collection_id = c.uuid
                    WHERE c.name = :collection AND {where}
                )
            """
        params = {'collection': collection, **filters}
        stmt: Any = text(sql)
        result = await session.exec(stmt, params=params)  # type: ignore[arg-type]
        return bool(result.scalar())

    @staticmethod
    async def get_metadata(session: AsyncSession, *, digest: SHA256B64, collection: str) -> List[Dict[str, Any]]:
        """
        Return cmetadata for all chunks belonging to a given digest within a collection.

        This is primarily used by tests to assert document-level metadata has been
        applied consistently across all embeddings.
        """
        sql = """
            SELECT e.cmetadata
            FROM langchain_pg_embedding e
            JOIN langchain_pg_collection c ON e.collection_id = c.uuid
            WHERE c.name = :collection AND e.cmetadata->>'digest' = :digest
            ORDER BY e.id
        """
        stmt: Any = text(sql)
        result = await session.exec(stmt, params={'collection': collection, 'digest': digest})
        # For text() statements, SQLModel returns a TupleResult; use .all() and index column 0
        rows = result.all()
        out: List[Dict[str, Any]] = []
        for row in rows:
            cm = row[0]
            if isinstance(cm, dict):
                out.append(cm)
            else:
                # Some drivers may return JSON string; try to load
                try:
                    parsed = json.loads(cm) if isinstance(cm, str) else None
                    if isinstance(parsed, dict):
                        out.append(parsed)
                except Exception:
                    pass
        return out

    @staticmethod
    async def delete(session: AsyncSession, *, digest: SHA256B64) -> None:
        """Delete all embeddings for a given logical document id (metadata.digest)."""
        if not digest:
            raise ValueError('digest must be a non-empty string')

        logger.info(f"Deleting embeddings with digest='{digest}'")

        delete_sql = "DELETE FROM langchain_pg_embedding WHERE cmetadata->>'digest' = :digest"

        stmt: Any = text(delete_sql)
        await session.exec(stmt, params={'digest': digest})  # type: ignore[arg-type]
        await session.commit()

        logger.success(f"Deleted embeddings for digest='{digest}'")
