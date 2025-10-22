#!/usr/bin/env bash
set -euo pipefail

echo '=== Running bootstrap: creating roles and schema ==='

postgres_user=${POSTGRES_USER:-postgres}
postgres_db=${POSTGRES_DB:-$postgres_user}

app_user=${VECTRA_APP_USER:-vectra_app_user}
app_password=${VECTRA_APP_PASSWORD:-app-user-password}
alembic_user=${VECTRA_ALEMBIC_USER:-vectra_alembic_user}
alembic_password=${VECTRA_ALEMBIC_PASSWORD:-alembic-user-password}
metis_user=${METIS_APP_USER:-metis_app_user}
metis_password=${METIS_APP_PASSWORD:-metis-app-password}

sql_escape_literal() {
  local raw=$1
  printf "'%s'" "${raw//\'/''}"
}

app_user_literal=$(sql_escape_literal "$app_user")
app_password_literal=$(sql_escape_literal "$app_password")
alembic_user_literal=$(sql_escape_literal "$alembic_user")
alembic_password_literal=$(sql_escape_literal "$alembic_password")
metis_user_literal=$(sql_escape_literal "$metis_user")
metis_password_literal=$(sql_escape_literal "$metis_password")

psql_args=(
  --username "$postgres_user"
  --dbname "$postgres_db"
  -v ON_ERROR_STOP=1
)

psql "${psql_args[@]}" <<SQL
DO \$bootstrap$
DECLARE
  app_user CONSTANT text := ${app_user_literal};
  app_password CONSTANT text := ${app_password_literal};
  alembic_user CONSTANT text := ${alembic_user_literal};
  alembic_password CONSTANT text := ${alembic_password_literal};
  metis_user CONSTANT text := ${metis_user_literal};
  metis_password CONSTANT text := ${metis_password_literal};
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'ddl_owner') THEN
    EXECUTE 'CREATE ROLE ddl_owner NOLOGIN';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'vectra_rw') THEN
    EXECUTE 'CREATE ROLE vectra_rw NOLOGIN';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'vectra_ro') THEN
    EXECUTE 'CREATE ROLE vectra_ro NOLOGIN';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'metis_rw') THEN
    EXECUTE 'CREATE ROLE metis_rw NOLOGIN';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'metis_client') THEN
    EXECUTE 'CREATE ROLE metis_client NOLOGIN';
  END IF;

  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = app_user) THEN
    EXECUTE format('CREATE ROLE %I LOGIN PASSWORD %L', app_user, app_password);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = alembic_user) THEN
    EXECUTE format('CREATE ROLE %I LOGIN PASSWORD %L', alembic_user, alembic_password);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = metis_user) THEN
    EXECUTE format('CREATE ROLE %I LOGIN PASSWORD %L', metis_user, metis_password);
  END IF;

  EXECUTE format('GRANT vectra_rw TO %I', app_user);
  EXECUTE format('GRANT ddl_owner TO %I', alembic_user);
  EXECUTE format('GRANT metis_client TO %I', metis_user);

  EXECUTE 'CREATE SCHEMA IF NOT EXISTS vectra AUTHORIZATION ddl_owner';
  EXECUTE 'GRANT USAGE ON SCHEMA vectra TO vectra_rw, vectra_ro, metis_rw';

  EXECUTE format(
    'ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA vectra GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO vectra_rw',
    alembic_user
  );
  EXECUTE format(
    'ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA vectra GRANT SELECT ON TABLES TO vectra_ro',
    alembic_user
  );
  EXECUTE format(
    'ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA vectra GRANT SELECT ON TABLES TO metis_rw',
    alembic_user
  );
  EXECUTE format(
    'ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA vectra GRANT USAGE, SELECT ON SEQUENCES TO vectra_rw, vectra_ro, metis_rw',
    alembic_user
  );
  EXECUTE format(
    'ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA vectra GRANT EXECUTE ON FUNCTIONS TO vectra_rw, vectra_ro',
    alembic_user
  );
END;
\$bootstrap$;

GRANT vectra_ro TO metis_client;
GRANT metis_rw TO metis_client;
SQL

echo '=== Bootstrap completed ==='
