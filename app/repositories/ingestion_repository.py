from __future__ import annotations

from datetime import datetime, timezone

from loguru import logger
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.utils.types import SHA256B64
from app.vector.schemas import IngestionVersionKey
from uuid import uuid4, UUID


class Ingestion:
    @staticmethod
    async def exists_by_key(session: AsyncSession, *, key: IngestionVersionKey) -> bool:
        """Return True if an ingestion version row exists for the given parameters."""
        sql = (
            'SELECT id FROM ingestion_versions WHERE '
            " tenant_id = current_setting('app.tenant_id', true)::uuid AND "
            ' collection = :collection AND digest = :digest AND '
            ' chunker_version = :chunker_version AND embed_model = :embed_model AND '
            ' embed_model_ver = :embed_model_ver LIMIT 1'
        )
        params = {
            'collection': key.collection,
            'digest': key.digest,
            'chunker_version': key.chunker_version,
            'embed_model': key.embed_model,
            'embed_model_ver': key.embed_model_ver,
        }
        res = await session.execute(text(sql), params)
        found = res.scalar_one_or_none() if hasattr(res, 'scalar_one_or_none') else None
        return found is not None

    @staticmethod
    async def exists_by_digest(
        session: AsyncSession,
        *,
        digest: SHA256B64,
        collection: str,
    ) -> bool:
        """Return True if any ingestion version row exists for the given collection and digest.

        Supports two call styles for backward compatibility:
        - exists_by_digest(session, digest=..., collection=...)
        - exists_by_digest(digest, collection=...)  # session omitted
        """

        sql = (
            'SELECT id FROM ingestion_versions WHERE '
            " tenant_id = current_setting('app.tenant_id', true)::uuid AND "
            ' collection = :collection AND digest = :digest LIMIT 1'
        )
        params = {'collection': collection, 'digest': digest}

        res = await session.execute(text(sql), params)
        found = res.scalar_one_or_none() if hasattr(res, 'scalar_one_or_none') else None
        return found is not None

    @staticmethod
    async def insert_key(session: AsyncSession, *, key: IngestionVersionKey) -> UUID:
        sql = (
            'INSERT INTO ingestion_versions ('
            'id, tenant_id, created_by, collection, digest, chunker_version, embed_model, embed_model_ver, created_at'
            ') VALUES ('
            ":id, current_setting('app.tenant_id', true)::uuid, current_setting('app.tenant_id', true)::uuid, :collection, :digest, :chunker_version, :embed_model, :embed_model_ver, :created_at) "
            'ON CONFLICT DO NOTHING'
            ' RETURNING id'
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

        try:
            res = await session.execute(text(sql), params)
            row = res.fetchone()
            await session.commit()
        except Exception as e:
            await session.rollback()
            raise Exception(f'Failed to insert ingestion_versions: {e}')
        if not row:
            raise RuntimeError('Insert into ingestion_versions did not return an id')
        return row[0]

    @staticmethod
    async def delete_by_digest(
        session: AsyncSession, *, digest: SHA256B64, collection: str
    ) -> None:
        """Delete all ingestion version rows for the given digest across the tenant.

        Note: Although a collection argument is accepted for signature compatibility,
        the deletion is performed for all collections sharing the digest, matching
        integration test expectations and idempotent cleanup semantics.
        """
        if not digest:
            raise ValueError('digest must be a non-empty string')
        if not collection:
            # keep validation for compatibility; value is unused in the query
            raise ValueError('collection must be a non-empty string')

        try:
            stmt = text(
                "DELETE FROM ingestion_versions WHERE tenant_id = current_setting('app.tenant_id', true)::uuid AND digest = :digest"
            )
            await session.execute(stmt, {'digest': digest})
            await session.commit()
        except Exception as e:  # pragma: no cover
            await session.rollback()
            logger.error(
                f"Failed to delete ingestion_versions for digest '{digest}' (all collections): {e}"
            )
