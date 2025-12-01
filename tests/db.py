from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Mapping

from sqlalchemy import URL, text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

from alembic import command
from alembic.config import Config
from core import db as core_db
from core.config import get_settings

PROJECT_ROOT = Path(__file__).resolve().parent.parent
INIT_SQL_DIR = PROJECT_ROOT / 'docker' / 'init'
TEST_SEED_DIR = PROJECT_ROOT / 'tests' / 'fixtures' / 'init_sql'
PGBOUNCER_AUTH_PASSWORD = 'pgbouncer_auth_password'


_RE_META = re.compile(r'^\s*\\')  # psql meta-commands: \set, \if, \getenv, \endif, ...
_RE_COMMENT = re.compile(r'^\s*--')  # SQL comments
_RE_TXN = re.compile(r'^\s*(BEGIN|COMMIT)\s*;?\s*$', re.IGNORECASE)
_RE_SET_LOCAL = re.compile(r'^\s*SET\s+LOCAL\s+app\.[a-z_]+\s+TO\s+:.+?;\s*$', re.IGNORECASE)
_RE_DOLLAR = re.compile(r'\$(?P<tag>[A-Za-z_][A-Za-z0-9_]*)?\$')
_RE_PLACEHOLDER = re.compile(r":'(?P<name>[A-Za-z_][A-Za-z0-9_]*)'")


def _build_sql_placeholder_replacements() -> dict[str, str]:
    replacements: dict[str, str] = {}
    replacements['pgbouncer_auth_password'] = PGBOUNCER_AUTH_PASSWORD
    return replacements


SQL_PLACEHOLDER_REPLACEMENTS = _build_sql_placeholder_replacements()


def _replace_psql_placeholders(sql_text: str, replacements: Mapping[str, str] | None) -> str:
    def _sub(match: re.Match[str]) -> str:
        name = match.group('name')
        value: str | None = None
        if replacements and name in replacements:
            value = replacements[name]
        else:
            value = os.environ.get(name)

        if value is None:
            raise ValueError(f"psql placeholder :'{name}' requires a value (set env or pass replacements)")

        escaped = value.replace("'", "''")
        return f"'{escaped}'"

    return _RE_PLACEHOLDER.sub(_sub, sql_text)


def _filter_psql_directives(sql_text: str, *, replacements: Mapping[str, str] | None = None) -> str:
    """
    Make a psql-oriented init script safe for asyncpg/SQLAlchemy:
      - drop psql meta-commands and comments
      - drop standalone BEGIN/COMMIT
      - drop SET LOCAL app.* lines
      - replace psql variables :'<name>' with literals
    """

    out_lines: list[str] = []
    in_dollar = False
    curr_tag: str | None = None

    for line in sql_text.splitlines():
        # update dollar-quote state (handles multiple occurrences on one line)
        for m in _RE_DOLLAR.finditer(line):
            tag = m.group('tag')
            if not in_dollar:
                in_dollar, curr_tag = True, tag
            else:
                # close only if tag matches (None matches None for $$)
                if curr_tag == tag:
                    in_dollar, curr_tag = False, None
        # Drop only when NOT inside a dollar-quoted block
        if not in_dollar:
            if _RE_META.match(line):  # \set, \getenv, \if, \endif, ...
                continue
            if _RE_COMMENT.match(line):  # -- comment
                continue
            if _RE_TXN.match(line):  # BEGIN; / COMMIT;
                continue
            if _RE_SET_LOCAL.match(line):  # SET LOCAL app.app_schema TO :'...';
                continue

        out_lines.append(line)

    sql_text = '\n'.join(out_lines).strip()
    if sql_text:
        sql_text += '\n'

    filtered = _replace_psql_placeholders(sql_text, replacements)
    if _RE_PLACEHOLDER.search(filtered):
        raise ValueError("psql placeholders like :'name' remain in SQL after filtering")

    return filtered


async def _load_seed_data(session: AsyncSession) -> None:
    if not TEST_SEED_DIR.exists():
        return

    for sql_path in sorted(TEST_SEED_DIR.glob('*.sql')):
        sql_text = _filter_psql_directives(sql_path.read_text(), replacements=SQL_PLACEHOLDER_REPLACEMENTS)
        if sql_text.strip():
            await session.exec(text(sql_text))  # type: ignore[no-matching-overload]
            await session.commit()


async def reset_database_state() -> None:
    alembic_url = os.environ.get('ALEMBIC_URL')
    if not alembic_url:
        return

    engine = create_async_engine(alembic_url)
    schema = get_settings().app_schema
    try:
        async with AsyncSession(engine) as session:
            await session.exec(text(f'TRUNCATE TABLE {schema}.documents RESTART IDENTITY CASCADE'))  # type: ignore[no-matching-overload]
            await session.exec(text(f'TRUNCATE TABLE {schema}.upload_jobs RESTART IDENTITY CASCADE'))  # type: ignore[no-matching-overload]
            await session.exec(text(f'TRUNCATE TABLE {schema}.ingestion_versions RESTART IDENTITY CASCADE'))  # type: ignore[no-matching-overload]
            await _load_seed_data(session)
    finally:
        await engine.dispose()

    await core_db.dispose_engines()


async def _execute_sql_scripts(connection_url: URL, directory: Path) -> None:
    if not directory.exists():
        return

    engine = create_async_engine(connection_url)
    try:
        async with AsyncSession(engine) as session:
            for sql_path in sorted(directory.glob('*.sql')):
                sql_text = _filter_psql_directives(sql_path.read_text(), replacements=SQL_PLACEHOLDER_REPLACEMENTS)
                if sql_text.strip():
                    await session.exec(text(sql_text))  # type: ignore[no-matching-overload]
                    await session.commit()
    finally:
        await engine.dispose()


async def prepare_database(base_url: URL) -> tuple[URL, URL]:
    await _execute_sql_scripts(base_url, INIT_SQL_DIR)

    app_url = base_url.set(username='vectra_user', password='app-password')
    alembic_url = base_url.set(username='alembic_user', password='alembic-password')
    return app_url, alembic_url


def run_migrations() -> None:
    alembic_cfg = Config(str(PROJECT_ROOT / 'alembic.ini'))
    alembic_cfg.set_main_option('script_location', str(PROJECT_ROOT / 'alembic'))
    command.upgrade(alembic_cfg, 'head')
