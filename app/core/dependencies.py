from __future__ import annotations

# Per-event-loop DatabaseManager registry
import asyncio
from contextlib import asynccontextmanager
from typing import AsyncIterator
from uuid import UUID

from sqlmodel.ext.asyncio.session import AsyncSession
import tenauth
from tenauth import AccessContext, build_access_scoped_session_dependency

from app.core.database import DatabaseManager

_db_managers_by_loop: dict[int, DatabaseManager] = {}


def get_database_manager() -> DatabaseManager:
    """Get a DatabaseManager bound to the current event loop.

    Avoids sharing async engines/sessions across event loops or threads.
    """
    loop = asyncio.get_running_loop()
    key = id(loop)
    mgr = _db_managers_by_loop.get(key)
    if mgr is None:
        mgr = DatabaseManager()
        _db_managers_by_loop[key] = mgr
    return mgr


require_auth = tenauth.require_auth
require_access_context = tenauth.require_access_context


async def apply_access_context(session: AsyncSession, *, tenant_id: UUID, user_id: UUID) -> None:
    """Compatibility wrapper that delegates to the shared access context applicator."""
    ctx = AccessContext(tenant_id=tenant_id, user_id=user_id)
    await tenauth.apply_access_context(session, access_context=ctx)


@asynccontextmanager
async def access_scoped_session_ctx(
    access_context: AccessContext,
) -> AsyncIterator[AsyncSession]:
    """Async context manager for a DB session with tenant/user GUCs applied.

    Use this in background tasks and services: `async with access_scoped_session_ctx(ctx) as session:`
    """
    db = get_database_manager()
    async with tenauth.access_scoped_session_ctx(
        session_factory=db.get_session,
        access_context=access_context,
    ) as session:
        yield session


def _session_factory():
    return get_database_manager().get_session()


access_scoped_session = build_access_scoped_session_dependency(_session_factory)


__all__ = [
    'get_database_manager',
    'require_auth',
    'access_scoped_session',
    'apply_access_context',
    'require_access_context',
    'access_scoped_session_ctx',
]
