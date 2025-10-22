#!/usr/bin/env bash
set -euo pipefail

echo '=== Ensuring database extensions ==='

postgres_user=${POSTGRES_USER:-postgres}
postgres_db=${POSTGRES_DB:-$postgres_user}

psql_args=(
  --username "$postgres_user"
  --dbname "$postgres_db"
  -v ON_ERROR_STOP=1
)

psql "${psql_args[@]}" <<SQL
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS vector;
SQL

echo '=== Extension setup completed ==='
