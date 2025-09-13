"""
Database session/engine management using SQLModel (+ SQLAlchemy async).

Provides DatabaseManager which encapsulates AsyncEngine lifecycle and safe AsyncSession access.
"""

from __future__ import annotations

import asyncio

from loguru import logger
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy import text
from sqlalchemy import event
from sqlmodel import SQLModel

from .config import get_settings
from .exceptions import RlsNotEnforcedError


class _SessionAcquire:
    """Internal async context manager that ensures the engine exists on the
    current loop before creating an AsyncSession, and closes it safely.
    """

    def __init__(self, manager: 'DatabaseManager') -> None:
        self._manager = manager
        self._session: AsyncSession | None = None

    async def __aenter__(self) -> AsyncSession:
        await self._manager._ensure_engine()
        self._session = self._manager._session_factory()  # type: ignore[operator]
        return self._session

    async def __aexit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001
        if self._session is None:
            return
        try:
            await self._session.close()
        except Exception as e:  # pragma: no cover
            logger.warning(f'Error closing DB session: {e}')
        finally:
            self._session = None


async def _ensure_models_load():
    try:
        from app.repositories import models as _  # noqa: F401
    except Exception as e:  # pragma: no cover
        logger.warning(
            f'Failed to import repositories.models before schema creation: {e}'
        )


async def assert_rls_enforced(conn) -> None:
    row = (
        await conn.execute(
            text(
                """
        SELECT rolsuper, rolbypassrls
        FROM pg_roles
        WHERE rolname = current_user
        """
            )
        )
    ).fetchone()
    rs = (await conn.execute(text('SHOW row_security'))).scalar_one()

    if not row:
        raise RuntimeError('Could not read pg_roles for current_user')

    rolsuper, rolbypassrls = row
    if rolsuper or rolbypassrls or rs.lower() != 'on':
        raise RlsNotEnforcedError(
            f'RLS NOT ENFORCED: rolsuper={rolsuper}, rolbypassrls={rolbypassrls}, row_security={rs}'
        )

    logger.debug('RLS enforced for current_user; row_security is ON')


class DatabaseManager:
    """
    Manages SQLAlchemy AsyncEngine and provides a clean interface for DB operations.

    Key guarantees:
    - An engine is always created on the current event loop.
    - If code runs on a different loop (e.g., per-test loops), the old engine is disposed
      and a new one is created transparently.
    - `get_session()` returns an async context manager yielding an AsyncSession.
    """

    def __init__(self) -> None:
        self._engine: AsyncEngine | None = None
        self._session_factory: async_sessionmaker[AsyncSession] | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._settings = get_settings()

    def _async_dsn(self) -> str:
        # Convert postgresql:// to postgresql+asyncpg:// for async engine
        dsn = self._settings.pg_vector_url.get_secret_value()
        if dsn.startswith('postgresql+asyncpg://'):
            return dsn
        if dsn.startswith('postgresql://'):
            return dsn.replace('postgresql://', 'postgresql+asyncpg://', 1)
        if dsn.startswith('postgres://'):
            return dsn.replace('postgres://', 'postgresql+asyncpg://', 1)
        return dsn

    async def _dispose_engine_safely(self) -> None:
        if self._engine is not None:
            try:
                await self._engine.dispose()
            finally:
                self._engine = None
                self._session_factory = None
                self._loop = None
                logger.debug('Database async engine disposed')

    async def _create_extensions(self):
        # Ensure pgcrypto and vector extensions are available (dev/test convenience).
        if not self._engine:
            raise RuntimeError('Engine not initialized')
        try:
            async with self._engine.begin() as conn:
                await conn.execute(text('CREATE EXTENSION IF NOT EXISTS pgcrypto;'))
                await conn.execute(text('CREATE EXTENSION IF NOT EXISTS vector;'))
        except Exception as e:  # pragma: no cover
            logger.warning(f'Could not ensure pgcrypto/vector extensions: {e}')

    async def _ensure_engine(self) -> None:
        current_loop = asyncio.get_running_loop()
        if self._engine is not None and self._loop is not current_loop:
            logger.debug('Recreating DB engine due to event-loop change')
            await self._dispose_engine_safely()

        if self._engine is None:
            self._engine = create_async_engine(
                self._async_dsn(), pool_size=5, max_overflow=5
            )
            self._session_factory = async_sessionmaker(
                self._engine, expire_on_commit=False, class_=AsyncSession
            )
            self._loop = current_loop
            logger.debug('Database async engine initialized')

            # Harden per-connection defaults: enforce RLS, unset tenant GUC, and set UTC
            @event.listens_for(self._engine.sync_engine, 'connect')
            def _on_connect(dbapi_connection, connection_record):  # pragma: no cover
                # For asyncpg's adapted cursor, context manager is not supported.
                # Use the raw cursor and call execute synchronously; SQLAlchemy adapts this for us.
                cur = dbapi_connection.cursor()
                cur.execute('SET row_security = on')
                cur.execute('RESET app.tenant_id')
                cur.execute("SET TIME ZONE 'UTC'")

    async def initialize(self) -> None:
        """Explicit initialization hook (optional for callers)."""
        await self._ensure_engine()
        if not self._engine:
            raise RuntimeError('Engine not initialized')
        async with self._engine.connect() as conn:
            await assert_rls_enforced(conn)
            await self._create_extensions()
            await conn.commit()

    async def _ensure_grants(self, conn):
        # Enable RLS and create tenant isolation policies for multi-tenant tables
        # documents
        await conn.execute(text('ALTER TABLE documents ENABLE ROW LEVEL SECURITY'))
        await conn.execute(text('ALTER TABLE documents FORCE ROW LEVEL SECURITY'))
        await conn.execute(text('DROP POLICY IF EXISTS tenant_isolation ON documents'))
        await conn.execute(
            text("""
                    CREATE POLICY tenant_isolation ON documents
                    USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
                    WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
                """)
        )
        # ingestion_versions
        await conn.execute(
            text('ALTER TABLE ingestion_versions ENABLE ROW LEVEL SECURITY')
        )
        await conn.execute(
            text('ALTER TABLE ingestion_versions FORCE ROW LEVEL SECURITY')
        )
        await conn.execute(
            text('DROP POLICY IF EXISTS tenant_isolation ON ingestion_versions')
        )
        await conn.execute(
            text("""
                    CREATE POLICY tenant_isolation ON ingestion_versions
                    USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
                    WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
                """)
        )
        # upload_jobs
        await conn.execute(text('ALTER TABLE upload_jobs ENABLE ROW LEVEL SECURITY'))
        await conn.execute(text('ALTER TABLE upload_jobs FORCE ROW LEVEL SECURITY'))
        await conn.execute(
            text('DROP POLICY IF EXISTS tenant_isolation ON upload_jobs')
        )
        await conn.execute(
            text("""
                    CREATE POLICY tenant_isolation ON upload_jobs
                    USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
                    WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
                """)
        )
        await conn.commit()

    async def ensure_schema(self) -> None:
        """Create SQLModel tables if they do not exist.

        Ensures models are imported so SQLModel.metadata is populated prior to create_all.
        """
        await self._ensure_engine()
        assert self._engine is not None

        await _ensure_models_load()

        # Use a dedicated connection to acquire an advisory lock outside the DDL transaction.
        async with self._engine.connect() as conn:
            await conn.execute(text('SELECT pg_advisory_lock(72727272)'))
            try:
                await conn.run_sync(SQLModel.metadata.create_all)
                await self._ensure_grants(conn)
            except Exception:
                await conn.rollback()
                raise
            finally:
                await conn.execute(text('SELECT pg_advisory_unlock(72727272)'))

    async def close(self) -> None:
        """Dispose the database async engine."""
        await self._dispose_engine_safely()

    def get_session(self) -> _SessionAcquire:
        """Return an async context manager that yields an AsyncSession.

        Usage:
            async with db_manager.get_session() as session:
                await session.execute(text("SELECT 1"))
        """
        return _SessionAcquire(self)
