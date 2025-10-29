from __future__ import annotations

import base64
import json
from uuid import UUID

import pytest
from fastapi import Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient
from tenauth.fastapi import require_auth
from tenauth.schemas import AuthContext

# Provided signed JWT (HS256) with claims:
# sub: 0c67622b-fcc5-4b58-9998-421b73e48df9
# tid: 00000000-0000-0000-0000-000000000000
# role: admin
# plan: dev
# iat, exp, iss: vecapi, aud: vecapi-clients
JWT_TOKEN = (
    'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.'
    'eyJzdWIiOiIwYzY3NjIyYi1mY2M1LTRiNTgtOTk5OC00MjFiNzNlNDhkZjkiLCJ0aWQiOiIwMDAwMDAwMC0wMDAwLTAwMDAtMDAwMC0wMDAwMDAwMDAwMDAiLCJyb2xlIjoiYWRtaW4iLCJwbGFuIjoiZGV2IiwiaWF0IjoxNzU4NzgxMDYwLCJleHAiOjE3NTg3ODQ2NjAsImlzcyI6InZlY2FwaSIsImF1ZCI6InZlY2FwaS1jbGllbnRzIn0.'
    'p_xH49ZNbT66729RiE7FHdqJbiR5AkUZiIph5sBNlEw'
)


def _decode_payload(token: str) -> dict:
    header, payload, _sig = token.split('.')
    padded = payload + '=' * (-len(payload) % 4)
    return json.loads(base64.urlsafe_b64decode(padded).decode('utf-8'))


def test_authcontext_from_token_parses_fields():
    ctx = AuthContext.from_token(JWT_TOKEN)
    assert ctx.sub == UUID('0c67622b-fcc5-4b58-9998-421b73e48df9')
    assert ctx.tid == UUID('00000000-0000-0000-0000-000000000000')
    assert ctx.role == 'admin'
    assert ctx.plan == 'dev'
    # pass-through standard claims
    assert ctx.iss == 'vecapi'
    assert ctx.aud == 'vecapi-clients'
    assert isinstance(ctx.iat, int)
    assert isinstance(ctx.exp, int)


def test_authcontext_matches_raw_payload():
    payload = _decode_payload(JWT_TOKEN)
    ctx = AuthContext.from_token(JWT_TOKEN)
    # Ensure parity with raw payload values
    assert str(ctx.sub) == payload['sub']
    assert str(ctx.tid) == payload['tid']
    assert ctx.role == payload['role']
    assert ctx.plan == payload['plan']
    assert ctx.iss == payload['iss']
    assert ctx.aud == payload['aud']


def test_require_auth_accepts_bearer_token():
    app = FastAPI()

    @app.get('/whoami')
    def whoami(auth: AuthContext = Depends(require_auth)):
        return {'sub': str(auth.sub), 'tid': str(auth.tid), 'role': auth.role}

    client = TestClient(app)
    r = client.get('/whoami', headers={'Authorization': f'Bearer {JWT_TOKEN}'})
    assert r.status_code == 200
    data = r.json()
    assert data['sub'] == '0c67622b-fcc5-4b58-9998-421b73e48df9'
    assert data['tid'] == '00000000-0000-0000-0000-000000000000'
    assert data['role'] == 'admin'


def test_require_auth_rejects_missing_header():
    app = FastAPI()

    @app.get('/secure')
    def secure(_auth: AuthContext = Depends(require_auth)):
        return {'ok': True}

    client = TestClient(app)
    r = client.get('/secure')
    assert r.status_code == 401


def test_require_auth_rejects_wrong_scheme():
    app = FastAPI()

    @app.get('/secure')
    def secure(_auth: AuthContext = Depends(require_auth)):
        return {'ok': True}

    client = TestClient(app)
    r = client.get('/secure', headers={'Authorization': f'Basic {JWT_TOKEN}'})
    assert r.status_code == 401


@pytest.mark.parametrize(
    'bad_token',
    [
        'not-a-jwt',
        # Missing sub
        'e30.e30.e30',
    ],
)
def test_authcontext_from_token_invalid_raises_401(bad_token: str):
    with pytest.raises(HTTPException) as exc:
        AuthContext.from_token(bad_token)
    assert exc.value.status_code == 401
