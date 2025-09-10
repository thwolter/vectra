from __future__ import annotations

import os
import typing as t

import typer


db = typer.Typer(help='Database management commands')


def _set_env_if_provided(env: str | None) -> None:
    """Set the ENV variable for pydantic settings before importing app modules."""
    if env:
        # pydantic-settings reads env vars at import-time of Settings
        os.environ['ENV'] = env


@db.command('drop-tables')
def drop_tables(
    yes: bool = typer.Option(
        False,
        '--yes',
        '-y',
        help='Do not prompt for confirmation',
    ),
    env: t.Optional[str] = typer.Option(
        None,
        '--env',
        help='Settings profile to use (development|production|testing)',
    ),
) -> None:
    """Drop all SQLModel tables in the configured database.

    This operation is destructive. It will remove all tables known to SQLModel
    metadata used by the application models.
    """
    if not yes:
        proceed = typer.confirm(
            'This will DROP ALL DATABASE TABLES. Do you want to continue?',
            default=False,
        )
        if not proceed:
            typer.echo('Aborted.')
            raise typer.Exit(code=1)

    _set_env_if_provided(env)

    # Import here (after potential env change)
    from loguru import logger
    from sqlmodel import SQLModel
    from app.core.database import DatabaseManager
    from sqlalchemy import text

    async def _run(*args: object, **kwargs: object) -> None:
        dbm = DatabaseManager()
        try:
            await dbm.initialize()
            # Ensure models are imported so metadata is populated
            try:
                from app.repositories import models as _  # noqa: F401
            except Exception as e:
                logger.warning(f'Could not import repositories.models: {e}')

            # Use the engine to drop all metadata tables and vectorstore tables
            assert dbm._engine is not None  # noqa: SLF001 - safe within CLI scope
            async with dbm._engine.begin() as conn:  # noqa: SLF001
                # Drop application tables managed by SQLModel
                await conn.run_sync(SQLModel.metadata.drop_all)
                # Also drop LangChain pgvector tables if they exist
                await conn.execute(
                    text('DROP TABLE IF EXISTS langchain_pg_embedding CASCADE')
                )
                await conn.execute(
                    text('DROP TABLE IF EXISTS langchain_pg_collection CASCADE')
                )
            typer.echo('All tables (including vectorstore) dropped successfully.')
        finally:
            await dbm.close()

    # Run async routine
    try:
        import anyio

        anyio.run(_run, None)
    except ModuleNotFoundError:
        # Fallback if anyio is not installed; use asyncio directly
        import asyncio

        asyncio.run(_run())
