#!/usr/bin/env bash

set -euo pipefail

if [[ -z "${PGBOUNCER_AUTH_PASSWORD:-}" ]]; then
    echo "PGBOUNCER_AUTH_PASSWORD must be set for pgBouncer auth role provisioning." >&2
    exit 1
fi

pgbouncer_auth_password_b64="$(printf '%s' "${PGBOUNCER_AUTH_PASSWORD}" | base64 | tr -d '\n')"

psql -v ON_ERROR_STOP=1 --username "${POSTGRES_USER}" --dbname "${POSTGRES_DB}" <<SQL
DO \$vectra_users\$
DECLARE
    app_user            text := 'app_user';
    app_password        text := 'app-password';
    alembic_user        text := 'alembic_user';
    alembic_password    text := 'alembic-password';
    pgbouncer_auth_user text := 'pgbouncer_auth';
    pgbouncer_auth_password text := convert_from(decode('$pgbouncer_auth_password_b64', 'base64'), 'UTF8');
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = app_user) THEN
        EXECUTE format('CREATE ROLE %I LOGIN PASSWORD %L', app_user, app_password);
    ELSE
        EXECUTE format('ALTER ROLE %I WITH LOGIN PASSWORD %L', app_user, app_password);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = alembic_user) THEN
        EXECUTE format('CREATE ROLE %I LOGIN PASSWORD %L', alembic_user, alembic_password);
    ELSE
        EXECUTE format('ALTER ROLE %I WITH LOGIN PASSWORD %L', alembic_user, alembic_password);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = pgbouncer_auth_user) THEN
        EXECUTE format('CREATE ROLE %I LOGIN PASSWORD %L', pgbouncer_auth_user, pgbouncer_auth_password);
    ELSE
        EXECUTE format('ALTER ROLE %I WITH LOGIN PASSWORD %L', pgbouncer_auth_user, pgbouncer_auth_password);
    END IF;

    EXECUTE format('GRANT vectra_rw TO %I', app_user);
    EXECUTE format('GRANT ddl_owner TO %I', alembic_user);
END;
\$vectra_users\$;
SQL
