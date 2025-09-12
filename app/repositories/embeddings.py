"""
Repositories for metadata-related data access.

Contains MetadataRepository responsible for metadata queries and updates.
"""

from typing import Any, Dict, List

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from sqlmodel import SQLModel

from loguru import logger

from app.utils.types import SHA256B64

_metadata = SQLModel.metadata


class Embeddings:
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
        params = {
            'collection': collection,
            'digest': digest,
            'metadata': __import__('json').dumps(metadata),
        }

        try:
            await session.execute(text(sql), params)
            await session.commit()
        except Exception as e:
            logger.error(f"Failed to update metadata for digest '{digest}': {e}")

    @staticmethod
    async def exists_by_digest(
        session: AsyncSession, *, digest: SHA256B64, collection: str
    ) -> bool:
        """
        Check if a document with the given digest exists in the collection.
        """
        sql = """
            SELECT e.id
            FROM langchain_pg_embedding e
            JOIN langchain_pg_collection c ON e.collection_id = c.uuid
            WHERE c.name = :collection AND e.cmetadata->>'digest' = :digest
            LIMIT 1
            """
        result = await session.execute(
            text(sql), {'collection': collection, 'digest': digest}
        )
        rows = result.fetchall()

        return len(rows) > 0

    @staticmethod
    async def exists_by_source(
        session: AsyncSession, *, source: str, collection: str
    ) -> bool:
        """
        Check if a document with the given source key exists in the collection.
        This is used by integration/E2E tests to verify embeddings by S3 source key.
        """
        sql = """
            SELECT e.id
            FROM langchain_pg_embedding e
            JOIN langchain_pg_collection c ON e.collection_id = c.uuid
            WHERE c.name = :collection AND e.cmetadata->>'source' = :source
            LIMIT 1
        """
        result = await session.execute(
            text(sql), {'collection': collection, 'source': source}
        )
        rows = result.fetchall()
        return len(rows) > 0

    @staticmethod
    async def get_metadata(
        session: AsyncSession, *, digest: SHA256B64, collection: str
    ) -> List[Dict[str, Any]]:
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
        result = await session.execute(
            text(sql), {'collection': collection, 'digest': digest}
        )
        rows = result.fetchall()
        out: List[Dict[str, Any]] = []
        for row in rows:
            cm = row[0] if row else None
            if isinstance(cm, dict):
                out.append(cm)
            else:
                # Some drivers may return JSON string; try to load
                try:
                    import json as _json

                    parsed = _json.loads(cm) if isinstance(cm, str) else None
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

        delete_sql = (
            "DELETE FROM langchain_pg_embedding WHERE cmetadata->>'digest' = :digest"
        )

        await session.execute(text(delete_sql), {'digest': digest})
        await session.commit()

        logger.success(f"Deleted embeddings for digest='{digest}'")
