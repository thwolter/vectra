#!/usr/bin/env python3

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = REPO_ROOT / '.env'
USERLIST_PATH = REPO_ROOT / 'docker' / 'pgbouncer' / 'userlist.txt'
USERNAME = 'pgbouncer_auth'
SCRAM_ITERATIONS = 4096


def load_env_value(name: str) -> str:
    if not ENV_PATH.exists():
        sys.exit(f'Missing {ENV_PATH}. Copy .env.example to .env and set {name}.')

    value: str | None = None
    for raw_line in ENV_PATH.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, candidate = line.split('=', 1)
        if key.strip() != name:
            continue
        candidate = candidate.strip()
        if candidate and candidate[0] == candidate[-1] and candidate.startswith(("'", '"')):
            candidate = candidate[1:-1]
        value = candidate
        break

    if not value:
        sys.exit(f'{name} is not set in {ENV_PATH}.')

    return value


def generate_scram_secret(password: str) -> str:
    salt = os.urandom(16)
    salted_password = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt,
        SCRAM_ITERATIONS,
    )
    client_key = hmac.new(salted_password, b'Client Key', hashlib.sha256).digest()
    stored_key = hashlib.sha256(client_key).digest()
    server_key = hmac.new(salted_password, b'Server Key', hashlib.sha256).digest()
    salt_b64 = base64.b64encode(salt).decode('ascii')
    stored_key_b64 = base64.b64encode(stored_key).decode('ascii')
    server_key_b64 = base64.b64encode(server_key).decode('ascii')
    return f'SCRAM-SHA-256${SCRAM_ITERATIONS}:{salt_b64}${stored_key_b64}:{server_key_b64}'


def main() -> None:
    password = load_env_value('PGBOUNCER_AUTH_PASSWORD')
    secret = generate_scram_secret(password)
    USERLIST_PATH.write_text(f'"{USERNAME}" "{secret}"\n')
    os.chmod(USERLIST_PATH, 0o600)
    print(f'Wrote SCRAM secret for {USERNAME} to {USERLIST_PATH}')


if __name__ == '__main__':
    main()
