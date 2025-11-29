#!/usr/bin/env bash

set -euo pipefail

if [[ -z "${PGBOUNCER_AUTH_PASSWORD:-}" ]]; then
    echo "PGBOUNCER_AUTH_PASSWORD must be set for pgBouncer auth role provisioning." >&2
    exit 1
fi

pgbouncer_auth_password_b64="$(printf '%s' "${PGBOUNCER_AUTH_PASSWORD}" | base64 | tr -d '\n')"
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

psql \
    -v ON_ERROR_STOP=1 \
    --set=PGBOUNCER_AUTH_PASSWORD_B64="${pgbouncer_auth_password_b64}" \
    --username "${POSTGRES_USER}" \
    --dbname "${POSTGRES_DB}" \
    --file "${script_dir}/030_vectra_users.sql"
