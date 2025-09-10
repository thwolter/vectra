"""
Repositories for metadata-related data access.

Contains MetadataRepository responsible for metadata queries and updates.
"""

from typing import Any, Dict, List

from sqlalchemy import text

from sqlmodel import SQLModel

from loguru import logger

from app.utils.types import SHA256B64

_metadata = SQLModel.metadata


class EmbeddingsRepository:
    """
    Data access layer for metadata operations.

    This class encapsulates all database operations related to document
    metadata, providing a clean separation between business logic and
    data access.

    Note: Ingestion version functionality lives in IngestionRepository; selected
    convenience methods delegate to it for backward compatibility in tests.
    """

    def __init__(self, db_manager: Any):
        self.db_manager = db_manager

    async def _ensure_db(self) -> None:
        if not self.db_manager.is_initialized:
            await self.db_manager.initialize()

    async def update_metadata(
        self,
        digest: SHA256B64,
        *,
        metadata: Dict[str, Any],
        collection: str,
        replace: bool = False,
    ) -> None:
        """
        Update metadata for all chunks of a document identified by digest, scoped by collection.

        Args:
            digest: Logical document identifier stored in cmetadata.digest.
            metadata: Partial or full metadata to apply to each chunk.
            collection: Vector collection name to scope the update.
            replace: If True, replace entirely (preserving digest). If False (default), merge keys into existing cmetadata (shallow).
        """
        if not metadata:
            return

        await self._ensure_db()

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

        async with self.db_manager.get_session() as session:
            try:
                await session.execute(text(sql), params)
                await session.commit()
            except Exception as e:
                logger.error(f"Failed to update metadata for digest '{digest}': {e}")

    async def exists_by_digest(self, digest: SHA256B64, *, collection: str) -> bool:
        """
        Check if a document with the given digest exists in the collection.
        """
        await self._ensure_db()

        async with self.db_manager.get_session() as session:
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

    async def exists_by_source(self, source: str, *, collection: str) -> bool:
        """
        Check if a document with the given source key exists in the collection.
        This is used by integration/E2E tests to verify embeddings by S3 source key.
        """
        await self._ensure_db()
        async with self.db_manager.get_session() as session:
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

    async def get_metadata(
        self, digest: SHA256B64, *, collection: str
    ) -> List[Dict[str, Any]]:
        """
        Return cmetadata for all chunks belonging to a given digest within a collection.

        This is primarily used by tests to assert document-level metadata has been
        applied consistently across all embeddings.
        """
        await self._ensure_db()
        sql = """
            SELECT e.cmetadata
            FROM langchain_pg_embedding e
            JOIN langchain_pg_collection c ON e.collection_id = c.uuid
            WHERE c.name = :collection AND e.cmetadata->>'digest' = :digest
            ORDER BY e.id
        """
        async with self.db_manager.get_session() as session:
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

    async def delete(self, digest: SHA256B64) -> None:
        """Delete all embeddings for a given logical document id (metadata.digest)."""
        if not digest:
            raise ValueError('digest must be a non-empty string')

        logger.info(f"Deleting embeddings with digest='{digest}'")

        if not self.db_manager.is_initialized:
            await self.db_manager.initialize()

        delete_sql = (
            "DELETE FROM langchain_pg_embedding WHERE cmetadata->>'digest' = :digest"
        )

        async with self.db_manager.get_session() as session:
            result = await session.execute(text(delete_sql), {'digest': digest})
            await session.commit()
            logger.info(
                f"Deleted rows from database for digest='{digest}': {getattr(result, 'rowcount', 'unknown')}"
            )

        # Best-effort: also instruct the vector to delete by metadata filter if supported
        try:
            # Newer langchain_postgres exposes a delete method that accepts a where filter
            self.vectorstore.delete(where={'digest': digest})  # type: ignore[arg-type]
        except Exception:
            # Ignore if not supported; DB delete above is authoritative
            pass

        logger.success(f"Deleted embeddings for digest='{digest}'")
