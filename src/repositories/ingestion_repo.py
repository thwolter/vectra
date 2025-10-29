from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from loguru import logger
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from tenauth.schemas import AccessContext

from utils.types import SHA256B64

from .exceptions import RecordNotFoundError
from .models import IngestionRecord
from .schemas import IngestionCreate


class IngestionRepository:
    """Persistence helpers for ingestion records."""

    def __init__(self) -> None:
        pass

    async def create(self, session: AsyncSession, *, data: IngestionCreate) -> IngestionRecord:
        access_ctx = AccessContext.from_session(session)
        record = IngestionRecord(
            created_by=access_ctx.user_id,
            tenant_id=access_ctx.tenant_id,
            document_id=data.document_id,
            job_id=data.job_id,
            collection=data.collection,
            chunker_model=data.chunker_model,
            chunker_version=data.chunker_version,
            chunker_params=data.chunker_params,
            embed_model=data.embed_model,
            embed_model_version=data.embed_model_version,
            embed_dim=data.embed_dim,
            digest=data.digest,
            fingerprint=data.fingerprint(),
            num_chunks=data.num_chunks,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        session.add(record)
        try:
            await session.commit()
            await session.refresh(record)
        except Exception as e:
            await session.rollback()
            raise Exception(f'Failed to create ingestion: {e}')
        return record

    async def get(self, session: AsyncSession, *, ingestion_id: UUID) -> IngestionRecord:
        ingestion: IngestionRecord | None = await session.get(IngestionRecord, ingestion_id)
        if ingestion is None:
            raise RecordNotFoundError(f'Ingestion {ingestion_id} not found')

        await session.refresh(ingestion, attribute_names=['document', 'job'])
        return ingestion

    async def delete(self, session: AsyncSession, *, ingestion_id: UUID) -> bool:
        try:
            rec = await self.get(session, ingestion_id=ingestion_id)
            if rec is None:
                return False
            await session.delete(rec)
            await session.commit()
            return True
        except Exception as e:
            await session.rollback()
            logger.error(f'Failed to delete ingestion version {ingestion_id}: {e}')
            return False

    async def find(
        self,
        session: AsyncSession,
        *,
        fingerprint: str,
        collection: str,
        digest: SHA256B64,
    ) -> IngestionRecord | None:
        statement = (
            select(IngestionRecord)
            .where(
                IngestionRecord.fingerprint == fingerprint,
                IngestionRecord.collection == collection,
                IngestionRecord.digest == digest,
            )
            .limit(1)
        )
        result = await session.exec(statement)
        return result.first()

    async def exists(
        self,
        session: AsyncSession,
        *,
        fingerprint: str,
        collection: str,
        digest: SHA256B64,
    ) -> bool:
        record = await self.find(session, fingerprint=fingerprint, collection=collection, digest=digest)
        return record is not None


ingestion_repository = IngestionRepository()
