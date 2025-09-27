from __future__ import annotations

import asyncio
import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlmodel import SQLModel

from alembic import context

# Ensure project root is on sys.path so `app` package is importable when running `alembic` CLI
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# This is the Alembic Config object, which provides access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Import application settings and models to populate target metadata
from app.core.config import get_settings  # noqa: E402
from app.repositories import (  # noqa: F401,E402  Ensure models are imported
    models as _models,
)

# Target metadata for autogeneration
target_metadata = SQLModel.metadata


def _get_async_db_url() -> str:
    """Return asyncpg database URL derived from app settings.

    Settings.pg_vector_url returns a SecretStr like postgresql://.... We need postgresql+asyncpg.
    """
    settings = get_settings()
    url = settings.pg_vector_url.get_secret_value()
    if url.startswith('postgres://'):
        url = url.replace('postgres://', 'postgresql://', 1)
    if url.startswith('postgresql://') and '+asyncpg' not in url:
        url = url.replace('postgresql://', 'postgresql+asyncpg://', 1)
    return url


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = _get_async_db_url()
    # For offline mode, Alembic prefers a sync driver URL, but modern Alembic can handle literal SQL generation.
    # We normalize to a sync-style URL for offline rendering.
    if url.startswith('postgresql+asyncpg://'):
        url = url.replace('postgresql+asyncpg://', 'postgresql://', 1)

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={'paramstyle': 'named'},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable: AsyncEngine = create_async_engine(
        _get_async_db_url(),
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
