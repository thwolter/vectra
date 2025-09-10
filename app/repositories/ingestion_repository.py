from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, cast as t_cast

from loguru import logger
from sqlalchemy import and_, select, text
from sqlalchemy.exc import IntegrityError
from sqlmodel import SQLModel

from app.repositories.models import IngestionVersion
from app.utils.types import SHA256B64
from app.vector.schemas import IngestionVersionKey
from uuid import uuid4

_metadata = SQLModel.metadata


class IngestionVersions:
    """
    Data access layer focused on ingestion idempotency/version tracking.

    This repository manages the `ingestion_versions` table, providing helpers to
    check for existing ingestions (fast idempotency) and to insert new records
    after successful ingestion.
    """

    def __init__(self, db_manager: Any):
        self.db_manager = db_manager

    async def _ensure_db(self) -> None:
        if not self.db_manager.is_initialized:
            await self.db_manager.initialize()

    async def ensure_ingestion_versions_table(self) -> None:
        """Create the ingestion_versions table if it does not exist using SQLModel metadata."""
        await self._ensure_db()
        await self.db_manager.ensure_schema()

    async def exists_by_key(self, key: IngestionVersionKey) -> bool:
        """Return True if an ingestion version row exists for the given parameters.

        Ensures the `ingestion_versions` table exists to avoid errors in first-run scenarios.
        """
        await self.ensure_ingestion_versions_table()
        async with self.db_manager.get_session() as session:
            iv_table = t_cast(Any, IngestionVersion).__table__
            stmt = (
                select(iv_table.c.id)
                .where(
                    and_(
                        iv_table.c.collection == key.collection,
                        iv_table.c.digest == key.digest,
                        iv_table.c.digest == key.digest,
                        iv_table.c.chunker_version == key.chunker_version,
                        iv_table.c.embed_model == key.embed_model,
                        iv_table.c.embed_model_ver == key.embed_model_ver,
                    )
                )
                .limit(1)
            )
            result = await session.execute(stmt)
            found = result.scalar_one_or_none()
        return found is not None

    async def exists_by_digest(
        self,
        *,
        digest: SHA256B64,
        collection: str,
    ) -> bool:
        """Return True if any ingestion version row exists for the given collection and digest.

        This is a convenience method for tests and operational checks where the
        full composite key (including content fingerprint and model versions) is
        not readily available.
        """
        await self.ensure_ingestion_versions_table()
        async with self.db_manager.get_session() as session:
            iv_table = t_cast(Any, IngestionVersion).__table__
            stmt = (
                select(iv_table.c.id)
                .where(
                    and_(
                        iv_table.c.collection == collection,
                        iv_table.c.digest == digest,
                    )
                )
                .limit(1)
            )
            result = await session.execute(stmt)
            found = result.scalar_one_or_none()
        return found is not None

    async def insert_Key(self, key: IngestionVersionKey) -> None:
        """Insert a new ingestion version row; if it already exists, do nothing.

        Uses IngestionVersionInsert/Key schema for normalized values.
        """
        await self.ensure_ingestion_versions_table()

        sql = (
            'INSERT INTO ingestion_versions '
            '(id, collection, digest, chunker_version, embed_model, embed_model_ver, created_at) '
            'VALUES (:id, :collection, :digest, :chunker_version, :embed_model, :embed_model_ver, :created_at) '
        )

        now_utc = datetime.now(timezone.utc)
        params = {
            'id': uuid4(),
            'collection': key.collection,
            'digest': key.digest,
            'chunker_version': key.chunker_version,
            'embed_model': key.embed_model,
            'embed_model_ver': key.embed_model_ver,
            'created_at': now_utc,
        }
        async with self.db_manager.get_session() as session:
            try:
                await session.execute(text(sql), params)
                await session.commit()
            except IntegrityError:
                await session.rollback()
                logger.warning(
                    f"Ingestion version for collection '{key.collection}' and digest '{key.digest}' already exists, skipping insert."
                )
            except Exception as e:
                logger.error(
                    f"Failed to insert ingestion version for collection '{key.collection}' and digest '{key.digest}': {e}"
                )

    async def delete_by_digest(self, *, digest: SHA256B64, collection: str) -> None:
        """Delete ingestion version rows for the given digest scoped to a collection.

        Rationale:
            - Deletions must be collection-aware to avoid removing records that
              belong to other collections for the same digest.
            - Ensures the table exists before attempting deletion.
        """
        if not digest:
            raise ValueError('digest must be a non-empty string')
        if not collection:
            raise ValueError('collection must be a non-empty string')

        await self.ensure_ingestion_versions_table()
        async with self.db_manager.get_session() as session:
            try:
                stmt = text(
                    'DELETE FROM ingestion_versions WHERE digest = :digest AND collection = :collection'
                )
                await session.execute(
                    stmt, {'digest': digest, 'collection': collection}
                )
                await session.commit()
            except Exception as e:  # pragma: no cover
                await session.rollback()
                logger.error(
                    f"Failed to delete ingestion_versions for digest '{digest}' and collection '{collection}': {e}"
                )
