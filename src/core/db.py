from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncContextManager, AsyncIterator
from uuid import UUID

import asyncpg
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession
from tenauth.schemas import AccessContext
from tenauth.session import access_scoped_session_ctx, apply_access_context

from .config import get_settings

_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        settings = get_settings()
        url = settings.async_postgres_url.get_secret_value()
        connect_args = {
            'server_settings': {'search_path': f'{settings.db_schema},public'},
        }
        _engine = create_async_engine(
            url,
            echo=settings.debug or False,
            pool_pre_ping=True,
            pool_recycle=3600,
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
            pool_timeout=settings.db_pool_timeout,
            connect_args=connect_args,
        )
    return _engine


@asynccontextmanager
async def _session_context() -> AsyncIterator[AsyncSession]:
    global _sessionmaker

    if _sessionmaker is None:
        _sessionmaker = async_sessionmaker(bind=get_engine(), class_=AsyncSession, expire_on_commit=False)

    session = _sessionmaker()
    try:
        yield session
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


def session_factory() -> AsyncContextManager[AsyncSession]:
    """Return a fresh async session context manager each time it is invoked."""
    return _session_context()


@asynccontextmanager
async def scoped_session(*, access_context: AccessContext, verify: bool = True) -> AsyncIterator[AsyncSession]:
    async with access_scoped_session_ctx(
        session_factory=session_factory,
        access_context=access_context,
        verify=verify,
    ) as session:
        exc: Exception | None = None
        try:
            yield session
        except Exception as err:
            exc = err
            raise
        finally:
            if exc is None:
                await session.commit()


async def pg_connect(tenant_id: UUID) -> asyncpg.Connection:
    settings = get_settings()
    dsn = settings.async_postgres_url.get_secret_value()
    server_settings = {
        'app.tenant_id': str(tenant_id),
        'search_path': f'{settings.db_schema},public',
    }
    return await asyncpg.connect(dsn=dsn, server_settings=server_settings, statement_cache_size=0)


async def ensure_access_context(session: AsyncSession, *, verify: bool = False) -> AccessContext:
    """Reapply tenant/user GUCs for sessions reused across transactions (e.g. pgbouncer)."""
    access_ctx = AccessContext.from_session(session)
    await apply_access_context(session, access_context=access_ctx, verify=verify)
    return access_ctx
