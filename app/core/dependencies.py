"""
Dependency factories for database access and repositories.

This module centralizes construction of the global DatabaseManager and
small factory helpers for repositories, following the project guideline:
"Collect Dependency factories in core/dependencies.py".
"""

from __future__ import annotations

from typing import AsyncIterator
from uuid import UUID
from fastapi import Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

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
    authorization: str = Header(..., alias='Authorization'),
) -> AuthContext:
    """Require Authorization and return AuthContext, else 401."""
    if not authorization:
        raise HTTPException(status_code=401, detail='Missing Authorization header')
    scheme, _, token = authorization.partition(' ')
    if scheme.lower() != 'bearer' or not token:
        raise HTTPException(status_code=401, detail='Invalid authorization scheme')
    auth = AuthContext.from_token(token)
    if auth is None:
        raise HTTPException(status_code=401, detail='Missing Authorization header')
    return auth


async def require_access_context(
    auth: AuthContext = Depends(require_auth),
) -> AccessContext:
    """Resolve tenant from a validated JWT."""
    return AccessContext(tenant_id=auth.tid, user_id=auth.sub)


async def apply_access_context(
    session: AsyncSession, *, tenant_id: UUID, user_id: UUID
) -> None:
    """Set Postgres GUCs and role for tenant/user on the current connection.

    - Sets app.tenant_id and app.user_id for RLS policies.
    - SET ROLE vecapi_rls to ensure RLS is enforced even if the base user is a superuser.
    - Values persist for the AsyncSession lifetime and are reset on exit by access_scoped_session.
    """
    # Persist on the connection (not LOCAL-to-transaction) for the session lifetime
    await session.execute(
        text("SELECT set_config('app.tenant_id', :tid, false)"), {'tid': str(tenant_id)}
    )
    await session.execute(
        text("SELECT set_config('app.user_id', :uid, false)"),
        {'uid': str(user_id)},
    )

    # Verify immediately
    db_user = (
        await session.execute(text("SELECT current_setting('app.user_id', true)"))
    ).scalar()
    db_tenant = (
        await session.execute(text("SELECT current_setting('app.tenant_id', true)"))
    ).scalar()
    if not db_user or not db_tenant:
        raise RuntimeError(
            f'Failed to bind access context: user_id={db_user!r}, tenant_id={db_tenant!r}'
        )
    if UUID(db_tenant) != tenant_id:
        raise RuntimeError(f'Tenant mismatch: {db_tenant} != {tenant_id}')
    if UUID(db_user) != user_id:
        raise RuntimeError(f'User mismatch: {db_user} != {user_id}')

    # Cache for repository usage across statement boundaries
    session.info['tenant_id'] = tenant_id
    session.info['user_id'] = user_id


async def access_scoped_session(
    tenant: AccessContext = Depends(require_access_context),
) -> AsyncIterator[AsyncSession]:
    """Yield an AsyncSession with tenant/user context applied for the request.

    Ensures Postgres GUCs are set for the session lifetime and reset afterwards
    to prevent leaks across pooled connections.
    """
    db = get_database_manager()
    async with db.get_session() as session:
        await apply_access_context(
            session, tenant_id=tenant.tenant_id, user_id=tenant.user_id
        )
        try:
            yield session
        finally:
            # Reset session-level GUCs so pooled connections don't leak tenant/user
            try:
                await session.execute(text('RESET app.user_id'))
                await session.execute(text('RESET app.tenant_id'))
            except Exception:
                # best-effort reset; closing the session will also drop settings when connection returns to pool
                pass
            session.info.pop('tenant_id', None)
            session.info.pop('user_id', None)


__all__ = [
    'get_database_manager',
    'require_auth',
    'access_scoped_session',
    'apply_access_context',
]
