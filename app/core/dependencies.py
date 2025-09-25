from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator
from uuid import UUID

from fastapi import Depends, Header, HTTPException
from sqlalchemy import text
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.schemas import AccessContext, AuthContext
from app.core.database import DatabaseManager

# Global database manager instance (singleton within process)
_db_manager: DatabaseManager | None = None


def get_database_manager() -> DatabaseManager:
    """Get the global DatabaseManager singleton.

    Ensures a single DatabaseManager instance is reused across the process.
    """
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
    return _db_manager


async def require_auth(
    authorization: str | None = Header(None, alias='Authorization'),
) -> AuthContext:
    """Require Authorization and return AuthContext, else 401.

    We intentionally make the header optional at the framework level to allow
    returning a 401 (Unauthorized) instead of FastAPI's default 422 when the
    header is missing, matching API contract and tests.
    """
    if not authorization:
        raise HTTPException(status_code=401, detail='Missing Authorization header')
    scheme, _, token = authorization.partition(' ')
    if scheme.lower() != 'bearer' or not token:
        raise HTTPException(status_code=401, detail='Invalid authorization scheme')
    auth = AuthContext.from_token(token)
    return auth


async def require_access_context(
    auth: AuthContext = Depends(require_auth),
) -> AccessContext:
    """Resolve tenant from a validated JWT."""
    return AccessContext(tenant_id=auth.tid, user_id=auth.sub)


async def verify(session, tenant_id, user_id):
    # Verify immediately
    res_user = await session.execute(text("SELECT current_setting('app.user_id', true)"))
    db_user = res_user.scalar()
    res_tenant = await session.execute(text("SELECT current_setting('app.tenant_id', true)"))
    db_tenant = res_tenant.scalar()
    if not db_user or not db_tenant:
        raise RuntimeError(f'Failed to bind access context: user_id={db_user!r}, tenant_id={db_tenant!r}')
    if UUID(db_tenant) != tenant_id:
        raise RuntimeError(f'Tenant mismatch: {db_tenant} != {tenant_id}')
    if UUID(db_user) != user_id:
        raise RuntimeError(f'User mismatch: {db_user} != {user_id}')


async def apply_access_context(session: AsyncSession, *, tenant_id: UUID, user_id: UUID) -> None:
    """Set Postgres GUCs and role for tenant/user on the current connection.

    - Sets app.tenant_id and app.user_id for RLS policies.
    - Values persist for the AsyncSession lifetime and are reset on exit by access_scoped_session.
    """
    # Persist on the connection (not LOCAL-to-transaction) for the session lifetime
    await session.execute(text("SELECT set_config('app.tenant_id', :tid, false)"), {'tid': str(tenant_id)})
    await session.execute(
        text("SELECT set_config('app.user_id', :uid, false)"),
        {'uid': str(user_id)},
    )

    await verify(session, tenant_id, user_id)

    session.info['tenant_id'] = tenant_id
    session.info['user_id'] = user_id


@asynccontextmanager
async def access_scoped_session_ctx(
    access_context: AccessContext,
) -> AsyncIterator[AsyncSession]:
    """Async context manager for a DB session with tenant/user GUCs applied.

    Use this in background tasks and services: `async with access_scoped_session_ctx(ctx) as session:`
    """
    db = get_database_manager()
    async with db.get_session() as session:
        await apply_access_context(session, tenant_id=access_context.tenant_id, user_id=access_context.user_id)
        try:
            yield session
        finally:
            try:
                await session.execute(text('RESET app.user_id'))
                await session.execute(text('RESET app.tenant_id'))
            except Exception:
                # best-effort; session close will drop connection settings
                pass
            session.info.pop('tenant_id', None)
            session.info.pop('user_id', None)


async def access_scoped_session(
    tenant: AccessContext = Depends(require_access_context),
) -> AsyncIterator[AsyncSession]:
    """Yield an AsyncSession with tenant/user context applied for the request.

    Ensures Postgres GUCs are set for the session lifetime and reset afterwards
    to prevent leaks across pooled connections.
    """
    async with access_scoped_session_ctx(tenant) as session:
        yield session


__all__ = [
    'get_database_manager',
    'require_auth',
    'access_scoped_session',
    'apply_access_context',
    'require_access_context',
    'access_scoped_session_ctx',
]
