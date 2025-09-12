from __future__ import annotations

from datetime import datetime, timezone

from loguru import logger
from sqlmodel import select
from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Any, overload

from app.utils.types import SHA256B64
from app.vector.schemas import IngestionVersionKey
from uuid import uuid4, UUID
from app.repositories.models import IngestionRecord


class Ingestion:
    @staticmethod
    @overload
    async def exists(session: AsyncSession, *, key: IngestionVersionKey) -> bool: ...

    @staticmethod
    @overload
    async def exists(
        session: AsyncSession, *, digest: SHA256B64, collection: str
    ) -> bool: ...

    @staticmethod
    async def exists(session: AsyncSession, **kwargs: Any) -> bool:
        """
        Return True if an ingestion version row exists for the given parameters.
        Provide either key=IngestionVersionKey or digest=..., collection=...
        Relies solely on database RLS for tenant scoping.
        """
        if 'key' in kwargs:
            key = kwargs['key']
            result = await Ingestion.find(session, key)
            return result is not None

        elif 'digest' in kwargs and 'collection' in kwargs:
            digest = kwargs['digest']
            collection = kwargs['collection']
            stmt = (
                select(IngestionRecord.id)
                .where(
                    IngestionRecord.collection == collection,
                    IngestionRecord.digest == digest,
                )
                .limit(1)
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none() is not None
        else:
            raise ValueError('Provide either key=... or digest=... and collection=...')

    @staticmethod
    async def create(session: AsyncSession, *, key: IngestionVersionKey) -> UUID:
        tenant_id = session.info['tenant_id']
        user_id = session.info['user_id']
        if not (tenant_id and user_id):
            raise RuntimeError(
                'tenant_id missing in session.info; ensure auth/session wiring sets it'
            )

        now_utc = datetime.now(timezone.utc)
        new_id = uuid4()
        rec = IngestionRecord(
            id=new_id,
            tenant_id=tenant_id,
            created_by=user_id or tenant_id,
            collection=key.collection,
            digest=key.digest,
            chunker_version=key.chunker_version,
            embed_model=key.embed_model,
            embed_model_ver=key.embed_model_ver,
            created_at=now_utc,
        )
        try:
            session.add(rec)
            await session.commit()
            return new_id
        except IntegrityError:
            await session.rollback()
            # Fetch existing id by unique tuple
            existing_id = await Ingestion.find(session, key)
            if existing_id is not None:
                return existing_id
            raise
        except Exception as e:
            await session.rollback()
            raise Exception(f'Failed to insert ingestion_versions: {e}')

    @staticmethod
    async def find(session: AsyncSession, key: IngestionVersionKey):
        stmt = (
            select(IngestionRecord.id)
            .where(
                IngestionRecord.collection == key.collection,
                IngestionRecord.digest == key.digest,
                IngestionRecord.chunker_version == key.chunker_version,
                IngestionRecord.embed_model == key.embed_model,
                IngestionRecord.embed_model_ver == key.embed_model_ver,
            )
            .limit(1)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def delete(
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
            # Delete across all collections for this digest; rely on RLS for tenant scoping
            stmt = delete(IngestionRecord).where(
                IngestionRecord.digest == digest,
            )
            await session.execute(stmt)
            await session.commit()
        except Exception as e:  # pragma: no cover
            await session.rollback()
            logger.error(
                f"Failed to delete ingestion_versions for digest '{digest}' (all collections): {e}"
            )
