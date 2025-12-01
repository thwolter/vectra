from contextlib import asynccontextmanager
from typing import AsyncIterator

from nexor.infrastructure import db as nexor_db
from sqlmodel.ext.asyncio.session import AsyncSession
from tenauth.schemas import AccessContext
from tenauth.session import apply_access_context

from core.config import get_settings


@asynccontextmanager
async def session_factory() -> AsyncIterator[AsyncSession]:
    """Return a fresh async session context manager each time it is invoked."""
    settings = get_settings()
    async with nexor_db.session_factory(settings) as session:
        yield session


@asynccontextmanager
async def scoped_session(*, access_context: AccessContext, verify: bool = True) -> AsyncIterator[AsyncSession]:
    settings = get_settings()
    async with nexor_db.scoped_session(
        settings=settings,
        access_context=access_context,
        verify=verify,
    ) as session:
        yield session


async def dispose_engines(*, loop=None) -> None:
    await nexor_db.dispose_engines(loop=loop)


async def test_db_connection() -> None:
    await nexor_db.test_db_connection(get_settings())


async def ensure_access_context(session: AsyncSession, *, verify: bool = False) -> AccessContext:
    """Reapply tenant/user GUCs for sessions reused across transactions (e.g. pgbouncer)."""
    access_ctx = AccessContext.from_session(session)
    await apply_access_context(session, access_context=access_ctx, verify=verify)
    return access_ctx
