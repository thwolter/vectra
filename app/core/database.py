from __future__ import annotations

import asyncio
import uuid
from typing import Final
from uuid import UUID

from loguru import logger
from sqlalchemy import String, bindparam, event, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

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
                # Optional safeguard for dev/test; set PG_STATEMENT_TIMEOUT='30s' etc.
                import os as _os

                _to = _os.getenv('PG_STATEMENT_TIMEOUT')
                if _to:
                    cur.execute(f"SET statement_timeout = '{_to}'")

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
        for tbl in APP_TENANT_TABLES:
            # Defensive whitelist check (no SQL injection via identifiers)
            if tbl not in APP_TENANT_TABLES:
                raise ValueError(f'Unexpected table name: {tbl}')

            await conn.execute(text(f'ALTER TABLE {tbl} ENABLE ROW LEVEL SECURITY'))
            await conn.execute(text(f'ALTER TABLE {tbl} FORCE ROW LEVEL SECURITY'))
            await conn.execute(text(f'DROP POLICY IF EXISTS tenant_isolation ON {tbl}'))
            await conn.execute(
                text(
                    f"""
                    CREATE POLICY tenant_isolation ON {tbl}
                    USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
                    WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
                    """
                )
            )

        # No commit here; transaction control handled by ensure_schema

    async def ensure_vs_grants(self, conn):
        # ---- LangChain PG tables: multi-tenant enablement (DRY over whitelist) ----
        # 1) Add tenant_id and set DEFAULT from GUC
        for tbl in LC_TENANT_TABLES:
            if tbl not in LC_TENANT_TABLES:  # defensive
                raise ValueError(f'Unexpected LC table name: {tbl}')
            await conn.execute(text(f'ALTER TABLE IF EXISTS {tbl} ADD COLUMN IF NOT EXISTS tenant_id uuid'))
            await conn.execute(
                text(
                    f"ALTER TABLE IF EXISTS {tbl} ALTER COLUMN tenant_id SET DEFAULT NULLIF(current_setting('app.tenant_id', true), '')::uuid"
                )
            )

        # 2) Helper function to set tenant from GUC (idempotent)
        await conn.execute(
            text(
                """
            CREATE OR REPLACE FUNCTION set_tenant_id_from_guc() RETURNS trigger
                LANGUAGE plpgsql AS
            $$
            BEGIN
                IF NEW.tenant_id IS NULL THEN
                    NEW.tenant_id := NULLIF(current_setting('app.tenant_id', true), '')::uuid;
                END IF;
                RETURN NEW;
            END;
            $$;
            """
            )
        )

        # 3) Attach BEFORE INSERT triggers and supporting indexes if tables exist
        per_table = {
            'langchain_pg_collection': {
                'trigger': 'trg_lc_collections_set_tenant',
                'index_sql': 'CREATE UNIQUE INDEX IF NOT EXISTS ux_lc_collection_tenant_name ON langchain_pg_collection (tenant_id, name)',
            },
            'langchain_pg_embedding': {
                'trigger': 'trg_lc_embeddings_set_tenant',
                'index_sql': 'CREATE INDEX IF NOT EXISTS ix_lc_embedding_tenant ON langchain_pg_embedding (tenant_id)',
            },
        }

        existing = {}
        for tbl in LC_TENANT_TABLES:
            existing[tbl] = bool((await conn.execute(text(f"SELECT to_regclass('{tbl}')"))).scalar())

        for tbl in LC_TENANT_TABLES:
            if not existing[tbl]:
                continue
            trg = per_table[tbl]['trigger']
            await conn.execute(text(f'DROP TRIGGER IF EXISTS {trg} ON {tbl}'))
            await conn.execute(
                text(
                    f"""
                CREATE TRIGGER {trg}
                BEFORE INSERT ON {tbl}
                FOR EACH ROW EXECUTE FUNCTION set_tenant_id_from_guc();
                """
                )
            )
            await conn.execute(text(per_table[tbl]['index_sql']))

        # 4) Temporarily disable RLS to allow NOT NULL enforcement checks
        for tbl in LC_TENANT_TABLES:
            if not existing[tbl]:
                continue
            await conn.execute(text(f'DROP POLICY IF EXISTS tenant_isolation ON {tbl}'))
            await conn.execute(text(f'ALTER TABLE {tbl} DISABLE ROW LEVEL SECURITY'))

        # 5) Try to enforce NOT NULL when safe (no NULLs present)
        await conn.execute(
            text(
                """
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'langchain_pg_collection' AND column_name = 'tenant_id'
                ) THEN
                    IF NOT EXISTS (
                        SELECT 1 FROM langchain_pg_collection WHERE tenant_id IS NULL
                    ) THEN
                        EXECUTE 'ALTER TABLE langchain_pg_collection ALTER COLUMN tenant_id SET NOT NULL';
                    END IF;
                END IF;
                IF EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'langchain_pg_embedding' AND column_name = 'tenant_id'
                ) THEN
                    IF NOT EXISTS (
                        SELECT 1 FROM langchain_pg_embedding WHERE tenant_id IS NULL
                    ) THEN
                        EXECUTE 'ALTER TABLE langchain_pg_embedding ALTER COLUMN tenant_id SET NOT NULL';
                    END IF;
                END IF;
            END$$;
            """
            )
        )

        # 6) Re-enable and force RLS with tenant policies
        for tbl in LC_TENANT_TABLES:
            if not existing[tbl]:
                continue
            await conn.execute(text(f'ALTER TABLE {tbl} ENABLE ROW LEVEL SECURITY'))
            await conn.execute(text(f'ALTER TABLE {tbl} FORCE ROW LEVEL SECURITY'))
            await conn.execute(text(f'DROP POLICY IF EXISTS tenant_isolation ON {tbl}'))
            await conn.execute(
                text(
                    f"""
                CREATE POLICY tenant_isolation ON {tbl}
                USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
                WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
                """
                )
            )

        # No commit here; transaction control handled by ensure_schema

    async def ensure_schema(self) -> None:
        """Create SQLModel tables if they do not exist (idempotent)."""
        await self._ensure_engine()
        assert self._engine is not None, 'Engine not initialized'

        await _ensure_models_load()

        # Fast-path: skip heavy DDL if core and vector tables already exist
        if self._schema_ready:
            return

        async with self._schema_lock:
            if await self.tables_exist_and_have_tenant_id():
                self._schema_ready = True
                return

            # Heavy path: run once across workers using an advisory lock
            async with self._engine.connect() as conn:
                await conn.execute(text('SELECT pg_advisory_lock(72727272)'))

                await _ensure_vs_tables()
                try:
                    await conn.run_sync(SQLModel.metadata.create_all)
                    await self._ensure_grants(conn)
                    await self.ensure_vs_grants(conn)
                    await conn.commit()
                    self._schema_ready = True
                except Exception:
                    await conn.rollback()
                    raise
                finally:
                    await conn.execute(text('SELECT pg_advisory_unlock(72727272)'))
                    logger.info('Database schema initialized')

    async def tables_exist_and_have_tenant_id(self):
        """
        Returns True if all required tables exist and each has a tenant_id column.
        """
        if not self._engine:
            raise RuntimeError('Engine not initialized')

        async with self._engine.connect() as conn:
            sql = text(
                """
                WITH required AS (
                    SELECT unnest(:tables) AS table_name
                ),
                present AS (
                  SELECT r.table_name
                  FROM required r
                  JOIN information_schema.tables t
                    ON t.table_name = r.table_name AND t.table_schema = 'public'
                ),
                tenant_check AS (
                  SELECT p.table_name,
                         EXISTS (
                           SELECT 1 FROM information_schema.columns c
                           WHERE c.table_schema='public'
                             AND c.table_name=p.table_name
                             AND c.column_name='tenant_id'
                         ) AS has_tenant
                  FROM present p
                )
                SELECT (
                    (SELECT COUNT(*) = (SELECT COUNT(*) FROM required) FROM present)
                )
                AND
                (
                    COALESCE((SELECT bool_and(has_tenant) FROM tenant_check), false)
                ) AS ok;
                """
            )
            # Bind array parameter with explicit PostgreSQL array type
            bp = bindparam('tables', value=list(REQUIRED_TABLES), type_=ARRAY(String()))
            sql = sql.bindparams(bp)
            return await conn.scalar(sql)

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
