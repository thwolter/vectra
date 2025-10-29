from typing import Any, overload

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


embeddings_repository = EmbeddingsRepository()
