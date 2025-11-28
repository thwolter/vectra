from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from loguru import logger
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from core.db import ensure_access_context
from utils.types import SHA256B64

from .exceptions import RecordNotFoundError
from .models import IngestionRecord
from .schemas import IngestionCreate, IngestionVersion


class IngestionRepository:
    """Persistence helpers for ingestion records."""

    def __init__(self) -> None:
        pass

    async def create(self, session: AsyncSession, *, data: IngestionCreate) -> IngestionRecord:
        access_ctx = await ensure_access_context(session)
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
            parser_fp=data.parser_fp,
            chunker_fp=data.chunker_fp,
            embedding_fp=data.embedding_fp,
            num_chunks=data.num_chunks,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        session.add(record)
        try:
            await session.flush()
            # Refresh before commit so RLS still sees tenant-scoped row.
            await session.refresh(record)
            await session.commit()
        except Exception as e:
            await session.rollback()
            raise Exception(f'Failed to create ingestion: {e}')
        return record

    async def get(self, session: AsyncSession, *, ingestion_id: UUID) -> IngestionRecord:
        await ensure_access_context(session, verify=False)
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
        collection: str,
        digest: SHA256B64,
        version: IngestionVersion | None = None,
        ) -> IngestionRecord | None:
        access_ctx = await ensure_access_context(session, verify=False)
        statement = (
            select(IngestionRecord)
            .where(
                IngestionRecord.tenant_id == access_ctx.tenant_id,
                IngestionRecord.collection == collection,
                IngestionRecord.digest == digest,
            )
            .limit(1)
        )
        if version is not None:
            statement = statement.where(
                IngestionRecord.parser_fp == version.parser_fp,
                IngestionRecord.chunker_fp == version.chunker_fp,
                IngestionRecord.embedding_fp == version.embedding_fp,
            )
        result = await session.exec(statement)
        return result.first()

    async def exists(
        self,
        session: AsyncSession,
        *,
        collection: str,
        digest: SHA256B64,
        version: IngestionVersion,
    ) -> bool:
        record = await self.find(session, collection=collection, digest=digest, version=version)
        return record is not None


ingestion_repository = IngestionRepository()
