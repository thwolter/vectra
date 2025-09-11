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

from app.api.schemas import TenantContext, AuthContext
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


async def get_current_auth(
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


async def get_current_tenant(
    auth: AuthContext = Depends(get_current_auth),
) -> TenantContext:
    """Resolve tenant from a validated JWT."""
    return TenantContext(tenant_id=auth.tid, user_id=auth.sub)


async def with_tenant(session: AsyncSession, tenant_id: UUID) -> None:
    """Set the Postgres LOCAL setting for the current tenant for this transaction.

    Uses set_config(..., is_local := true) so the value resets on COMMIT/ROLLBACK and
    does not leak across pooled connections. Parameter binding is supported with
    set_config, unlike `SET LOCAL ...` with asyncpg.
    Also caches the tenant_id in `session.info` for repositories to bind directly.
    """
    # Use set_config to safely bind the tenant id without string interpolation.
    await session.execute(
        text("SELECT set_config('app.tenant_id', :tid, true)"), {'tid': str(tenant_id)}
    )
    # Cache for repository usage across statement boundaries
    session.info['tenant_id'] = tenant_id


async def tenant_scoped_session(
    tenant: TenantContext = Depends(get_current_tenant),
) -> AsyncIterator[AsyncSession]:
    """Yield an AsyncSession with SET LOCAL app.tenant_id applied for the request.

    Routers/services should depend on this and pass the provided session to repositories.
    """
    db = get_database_manager()
    async with db.get_session() as session:
        await with_tenant(session, tenant.tenant_id)
        # Cache user_id for repositories to populate created_by
        session.info['user_id'] = getattr(tenant, 'user_id', None)
        yield session


__all__ = [
    'get_database_manager',
    'get_current_auth',
    'tenant_scoped_session',
    'with_tenant',
]
