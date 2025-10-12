from __future__ import annotations

import os
import sys
from logging.config import fileConfig
from pathlib import Path
from typing import Any, cast

from dotenv import dotenv_values
from sqlalchemy import engine_from_config, pool, text
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

from app.core.db_schema import APP_SCHEMA  # noqa: E402
from app.repositories import (  # noqa: F401,E402  Ensure models import for metadata
    models as _models,
)

target_metadata = SQLModel.metadata


def _collect_env() -> dict[str, str]:
    merged: dict[str, str] = {}
    candidate = _PROJECT_ROOT / '.env'
    if candidate.exists():
        for key, value in dotenv_values(candidate).items():
            if value is not None:
                merged[key] = value
    return merged


def _normalize_sync_url(url: str) -> str:
    if url.startswith('postgres://'):
        url = url.replace('postgres://', 'postgresql://', 1)
    if url.startswith('postgresql+asyncpg://'):
        url = url.replace('postgresql+asyncpg://', 'postgresql+psycopg2://', 1)
    return url


env_values = _collect_env()

alembic_url = env_values.get('ALEMBIC_DATABASE_URL') or os.getenv('ALEMBIC_DATABASE_URL')
if alembic_url is None:
    raise RuntimeError(
        'ALEMBIC_DATABASE_URL must be defined in .env, or the environment for Alembic migrations.'
    )

config.set_main_option('sqlalchemy.url', _normalize_sync_url(alembic_url))


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option('sqlalchemy.url')
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        include_schemas=True,
        version_table='alembic_version',
        version_table_schema=APP_SCHEMA,
        dialect_opts={'paramstyle': 'named'},
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    section = cast(dict[str, Any], config.get_section(config.config_ini_section) or {})
    connectable = engine_from_config(section, prefix='sqlalchemy.', poolclass=pool.NullPool)

    with connectable.connect() as connection:
        connection.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{APP_SCHEMA}"'))
        connection.commit()
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_schemas=True,
            version_table='alembic_version',
            version_table_schema=APP_SCHEMA,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
