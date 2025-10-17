from __future__ import annotations

import asyncio
import uuid
from typing import Final
from uuid import UUID

from loguru import logger
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.db_schema import APP_SCHEMA
from app.vector.factory import get_vectorstore
from app.vector.models import IngestorSettings

from .config import get_settings
from .exceptions import RlsNotEnforcedError

# Application tables that must be tenant-scoped via RLS/policies
APP_TENANT_TABLES: Final[tuple[str, ...]] = (
    'documents',
    'ingestion_versions',
    'upload_jobs',
)

# LangChain vectorstore tables that must be tenant-scoped
LC_TENANT_TABLES: Final[tuple[str, ...]] = (
    'langchain_pg_collection',
    'langchain_pg_embedding',
)

# Tables we require to exist and be tenant-scoped
REQUIRED_TABLES = APP_TENANT_TABLES + LC_TENANT_TABLES


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
        raise RuntimeError(f'Could not import models: {e}')


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

    logger.success('RLS enforced for current_user; row_security is ON')


async def _ensure_vs_tables():
    logger.info('Ensuring vectorstore tables')
    vs = get_vectorstore(
        collection=str(uuid.uuid4()), tenant_id=UUID('00000000-0000-0000-0000-000000000000'), config=IngestorSettings()
    )
    vs.delete_collection()


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
        # Fast-path flags for schema initialization
        self._schema_ready: bool = False
        self._schema_lock: asyncio.Lock = asyncio.Lock()

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
        """No-op: extensions must be created by Alembic migrations, not at runtime."""
        return None

    async def _ensure_engine(self) -> None:
        if self._engine is None:
            current_loop = asyncio.get_running_loop()
            self._engine = create_async_engine(self._async_dsn(), pool_size=5, max_overflow=5, pool_pre_ping=True)
            self._session_factory = async_sessionmaker(self._engine, expire_on_commit=False, class_=AsyncSession)
            self._loop = current_loop
            logger.debug(f'Database async engine initialized on loop_id={id(current_loop)}')

            # Harden per-connection defaults: enforce RLS, unset tenant GUC, and set UTC
            @event.listens_for(self._engine.sync_engine, 'connect')
            def _on_connect(dbapi_connection, connection_record):  # pragma: no cover
                # For asyncpg's adapted cursor, context manager is not supported.
                # Use the raw cursor and call execute synchronously; SQLAlchemy adapts this for us.
                cur = dbapi_connection.cursor()
                cur.execute('SET row_security = on')
                cur.execute('RESET app.tenant_id')
                cur.execute("SET TIME ZONE 'UTC'")
                cur.execute(f'SET search_path = {APP_SCHEMA}, public')
                # Optional safeguard for dev/test; set PG_STATEMENT_TIMEOUT='30s' etc.
                import os as _os

                _to = _os.getenv('PG_STATEMENT_TIMEOUT')
                if _to:
                    cur.execute(f"SET statement_timeout = '{_to}'")

    async def initialize(self) -> None:
        """Explicit initialization hook (optional for callers).

        Note: All schema changes are managed via Alembic migrations. This method
        must not execute any DDL. It only initializes the engine and asserts
        that RLS is enforced at the connection/session level.
        """
        await self._ensure_engine()
        if not self._engine:
            raise RuntimeError('Engine not initialized')
        async with self._engine.connect() as conn:
            await assert_rls_enforced(conn)
            await conn.commit()

    async def _ensure_grants(self, conn):
        """No-op: RLS/policies are managed via Alembic migrations, not at runtime."""
        return None

    async def ensure_vs_grants(self, conn):
        """No-op: Vectorstore (LangChain) table grants/policies should be managed via Alembic or vendor migrations.

        Runtime DDL for vendor tables has been removed to ensure strict separation of concerns.
        """
        return None

    async def ensure_schema(self) -> None:
        """Validate that the database schema is initialized via Alembic.

        This method performs no DDL. It only checks that Alembic has applied
        at least one migration and that RLS is enforced on the connection.
        """
        await self._ensure_engine()
        assert self._engine is not None, 'Engine not initialized'

        if self._schema_ready:
            return

        async with self._schema_lock:
            async with self._engine.connect() as conn:
                # Assert RLS settings at session level
                await assert_rls_enforced(conn)

            self._schema_ready = True

    async def tables_exist_and_have_tenant_id(self):
        """Quick readiness check for required tables and tenant_id column.

        Avoids any DDL; uses lightweight information_schema queries per table.
        """
        if not self._engine:
            raise RuntimeError('Engine not initialized')

        async with self._engine.connect() as conn:
            for tbl in REQUIRED_TABLES:
                # Table exists?
                exists = await conn.scalar(
                    text('SELECT to_regclass(:regcls) IS NOT NULL'),
                    {'regcls': f'{APP_SCHEMA}.{tbl}'},
                )
                if not exists:
                    return False
                # tenant_id column exists?
                col_exists = await conn.scalar(
                    text(
                        """
                        SELECT EXISTS (
                          SELECT 1
                          FROM information_schema.columns
                          WHERE table_schema=:schema AND table_name=:tbl AND column_name='tenant_id'
                        )
                        """
                    ),
                    {'tbl': tbl, 'schema': APP_SCHEMA},
                )
                if not col_exists:
                    return False
            return True

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
