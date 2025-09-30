from __future__ import annotations

import base64
import hmac
import json
import os
import time
import typing as t
from hashlib import sha256
from uuid import UUID, uuid4

import typer

auth = typer.Typer(help='Authentication utilities')


def _set_env_if_provided(env: str | None) -> None:
    if env:
        os.environ['ENV'] = env


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode('utf-8').rstrip('=')


def _sign_hs256(secret: str, message: bytes) -> str:
    sig = hmac.new(secret.encode('utf-8'), msg=message, digestmod=sha256).digest()
    return _b64url(sig)


async def _discover_tenant_id() -> UUID | None:
    """Try to auto-discover a tenant_id from existing records.

    Checks a few tables for any row and returns its tenant_id. Returns None if
    no tenant_id can be found without erroring out.
    """
    try:
        from sqlalchemy import text

        from app.core.database import DatabaseManager

        dbm = DatabaseManager()
        await dbm.initialize()
        try:
            assert dbm._engine is not None  # noqa: SLF001
            async with dbm._engine.connect() as conn:  # noqa: SLF001
                # Prefer documents table (most likely populated)
                for table in (
                    'documents',
                    'upload_jobs',
                    'ingestion_versions',
                    'langchain_pg_collection',
                    'langchain_pg_embedding',
                ):
                    try:
                        res = await conn.execute(text(f'SELECT tenant_id FROM {table} LIMIT 1'))
                        row = res.fetchone()
                        if row and row[0]:
                            return UUID(str(row[0]))
                    except Exception:
                        # table may not exist; ignore
                        continue
        finally:
            await dbm.close()
    except Exception:
        return None
    return None


@auth.command('generate')
def generate(
    tenant_id: t.Optional[UUID] = typer.Option(None, '--tenant-id', help='Tenant ID (UUID) to embed in JWT'),
    user_id: t.Optional[UUID] = typer.Option(None, '--user-id', help='User ID (UUID) to embed in JWT'),
    role: t.Optional[str] = typer.Option('admin', '--role', help='Role claim (e.g., owner|admin|editor|viewer)'),
    scopes: t.Optional[str] = typer.Option(None, '--scopes', help='Space-separated scopes string'),
    plan: t.Optional[str] = typer.Option('dev', '--plan', help='Plan/entitlements identifier'),
    iss: t.Optional[str] = typer.Option(None, '--iss', help='Override issuer claim'),
    aud: t.Optional[str] = typer.Option(None, '--aud', help='Override audience claim'),
    ttl: int = typer.Option(None, '--ttl', help='TTL in seconds for exp (defaults from settings)'),
    env: t.Optional[str] = typer.Option(None, '--env', help='Settings profile (development|production|testing)'),
    pretty: bool = typer.Option(False, '--pretty', help='Pretty-print decoded payload after token'),
) -> None:
    """Generate a signed JWT compatible with AuthContext.

    Auto-chooses sensible defaults:
    - tenant_id: discovered from DB if available, otherwise all-zero UUID
    - user_id: random UUID4
    - role: admin
    - iss/aud/ttl: from application settings unless overridden

    Outputs the compact JWT to stdout. Optionally prints the payload for inspection.
    """
    _set_env_if_provided(env)

    # Lazy import settings after ENV possibly set
    from app.core.config import get_settings

    settings = get_settings()

    now = int(time.time())
    ttl_seconds = ttl if ttl is not None else settings.jwt_ttl_seconds

    # Auto-discover tenant if not provided
    resolved_tenant: UUID
    if tenant_id is None:
        import asyncio

        try:
            resolved = asyncio.run(_discover_tenant_id())
        except RuntimeError:
            # Already inside event loop; use anyio
            import anyio

            # Define a wrapper that matches anyio.run's expected callable signature
            # i.e., a function accepting arbitrary args and returning an Awaitable
            def _runner(*_: object, **__: object) -> t.Awaitable[UUID | None]:
                return _discover_tenant_id()

            resolved = anyio.run(_runner)
        resolved_tenant = resolved or UUID('ae579baf-91c2-4497-abf5-44867e06c7a1')
    else:
        resolved_tenant = tenant_id

    resolved_user = user_id or uuid4()

    payload: dict[str, t.Any] = {
        'sub': str(resolved_user),
        'tid': str(resolved_tenant),
        'role': role,
        'plan': plan,
        'iat': now,
        'exp': now + int(ttl_seconds),
        'iss': iss or settings.jwt_issuer,
        'aud': aud or settings.jwt_audience,
    }

    if scopes:
        payload['scopes'] = [s for s in scopes.split(' ') if s]

    header = {'alg': 'HS256', 'typ': 'JWT'}

    header_b64 = _b64url(json.dumps(header, separators=(',', ':'), ensure_ascii=False).encode('utf-8'))
    payload_b64 = _b64url(json.dumps(payload, separators=(',', ':'), ensure_ascii=False).encode('utf-8'))

    signing_input = f'{header_b64}.{payload_b64}'.encode('utf-8')
    secret = settings.jwt_secret.get_secret_value()
    signature_b64 = _sign_hs256(secret, signing_input)

    token = f'{header_b64}.{payload_b64}.{signature_b64}'
    typer.echo(token)

    if pretty:
        typer.echo('\nDecoded payload:')
        typer.echo(json.dumps(payload, indent=2))
