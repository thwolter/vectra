from __future__ import annotations

import base64
import json
from uuid import UUID

from fastapi import HTTPException
from loguru import logger
from pydantic import BaseModel, Field
from sqlmodel.ext.asyncio.session import AsyncSession


class AccessContext(BaseModel):
    tenant_id: UUID
    user_id: UUID

    @classmethod
    def from_session(cls, session: AsyncSession) -> 'AccessContext':
        """Construct TenantContext from an AsyncSession.

        Expects the session to have `tenant_id` (and optionally `user_id`) set in
        `session.info` by the request/fixture layer. Raises a ValueError if the
        tenant_id is missing.
        """
        try:
            tenant_id = session.info.get('tenant_id')  # type: ignore[assignment]
            user_id = session.info.get('user_id')  # type: ignore[assignment]
            if tenant_id is None:
                raise ValueError('tenant_id missing in session.info')
            if user_id is None:
                raise ValueError('user_id missing in session.info')
            return cls(tenant_id=tenant_id, user_id=user_id)
        except Exception as e:
            raise ValueError(f'Failed to get tenant_id and user_id from session: {e}')


class AuthContext(BaseModel):
    """
    Lightweight JWT auth context extracted from Authorization: Bearer <token>.

    Fields follow the required attributes:
    - sub: user_id (UUID)
    - tid: tenant_id (UUID)
    - role: role string (owner|admin|editor|viewer)
    - scopes: list[str] fine-grained permissions
    - plan: optional plan/entitlements string or dict
    - iat, exp, iss, aud: standard JWT fields (kept as-is)
    """

    sub: UUID = Field(..., description='User ID')
    tid: UUID = Field(..., description='Tenant ID')
    role: str | None = None
    scopes: list[str] | None = None
    plan: str | dict | None = None
    iat: int | None = None
    exp: int | None = None
    iss: str | None = None
    aud: str | list[str] | None = None

    @classmethod
    def from_token(cls, token: str) -> 'AuthContext':
        """Parse JWT (without signature verification) into an AuthContext."""
        try:
            parts = token.split('.')
            if len(parts) < 2:
                raise ValueError('Malformed JWT')

            payload_bytes = base64.urlsafe_b64decode(parts[1] + '=' * (-len(parts[1]) % 4))
            payload = json.loads(payload_bytes.decode('utf-8'))

            sub = UUID(payload.get('sub')) if payload.get('sub') else None
            tid = UUID(payload.get('tid')) if payload.get('tid') else None
            if not sub or not tid:
                raise ValueError('Missing sub/tid in token')

            scopes = payload.get('scopes')
            if isinstance(scopes, str):
                scopes = [s.strip() for s in scopes.split(' ') if s.strip()]

            data = {k: payload.get(k) for k in ('role', 'iat', 'exp', 'iss', 'aud')}
            data.update(
                sub=sub,
                tid=tid,
                scopes=scopes,
                plan=payload.get('plan') or payload.get('entitlements'),
            )
            return cls(**data)

        except Exception as e:
            logger.warning(f'Failed to parse JWT: {e}')
            raise HTTPException(status_code=401, detail='Invalid token')
