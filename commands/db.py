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


@db.command('unlock')
def unlock(
    key: t.Optional[int] = typer.Option(
        None,
        '--key',
        '-k',
        help='Advisory lock key to unlock. If omitted, unlocks all locks for the session.',
    ),
    env: t.Optional[str] = typer.Option(
        None,
        '--env',
        help='Settings profile to use (development|production|testing)',
    ),
) -> None:
    """Unlock a PostgreSQL advisory lock safely outside any failed transaction.

    Examples:
    - Unlock a specific key: `python manage.py db unlock -k 72727272`
    - Unlock all locks for the session: `python manage.py db unlock`
    """
    _set_env_if_provided(env)

    # Import here (after potential env change)
    from app.core.database import DatabaseManager
    from sqlalchemy import text

    async def _run(*_args: object, **_kwargs: object) -> None:
        dbm = DatabaseManager()
        try:
            await dbm.initialize()
            assert dbm._engine is not None  # noqa: SLF001 - CLI scope
            # Open a fresh connection, no failed transaction context
            async with dbm._engine.connect() as conn:  # noqa: SLF001
                if key is None:
                    # Run outside an explicit transaction
                    await conn.exec_driver_sql('SELECT pg_advisory_unlock_all()')
                    typer.echo(
                        'Unlocked all advisory locks for the session (pg_advisory_unlock_all)'
                    )
                else:
                    res = await conn.execute(
                        text('SELECT pg_advisory_unlock(:key)'), {'key': key}
                    )
                    row = res.fetchone()
                    unlocked = bool(row[0]) if row else False
                    typer.echo(f'pg_advisory_unlock({key}) -> {unlocked}')
        finally:
            await dbm.close()

    try:
        import anyio

        anyio.run(_run, None)
    except ModuleNotFoundError:
        import asyncio

        asyncio.run(_run())


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
