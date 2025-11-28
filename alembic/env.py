import os
from logging.config import fileConfig
from pathlib import Path
from typing import Any, cast

from dotenv import dotenv_values
from sqlalchemy import engine_from_config, pool, text
from sqlmodel import SQLModel

from alembic import context
from core.config import get_settings

project_root = Path(__file__).resolve().parent.parent

settings = get_settings()

migration_env_path = project_root / '.env'
env_values = dotenv_values(migration_env_path) if migration_env_path.exists() else {}

# This is the Alembic Config object, which provides access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

from repositories import (  # noqa: F401,E402  Ensure models import for metadata
    models as _models,
)

target_metadata = SQLModel.metadata


def _normalize_sync_url(url: str) -> str:
    # Trim accidental whitespace that can produce invalid DB names like "test "
    url = url.strip()
    if url.startswith('postgres://'):
        url = url.replace('postgres://', 'postgresql://', 1)
    if url.startswith('postgresql+asyncpg://'):
        url = url.replace('postgresql+asyncpg://', 'postgresql+psycopg2://', 1)
    return url


alembic_url = os.getenv('ALEMBIC_DATABASE_URL') or env_values.get('ALEMBIC_DATABASE_URL')
if alembic_url is None:
    raise RuntimeError('ALEMBIC_DATABASE_URL must be defined in .env, or the environment for Alembic migrations.')

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
        version_table_schema=settings.db_schema,
        dialect_opts={'paramstyle': 'named'},
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    section = cast(dict[str, Any], config.get_section(config.config_ini_section) or {})
    connectable = engine_from_config(section, poolclass=pool.NullPool)

    db_schema = settings.db_schema

    with connectable.connect() as connection:
        connection.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{db_schema}"'))
        connection.commit()
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_schemas=True,
            version_table='alembic_version',
            version_table_schema=db_schema,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
