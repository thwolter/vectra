\set ON_ERROR_STOP on

\echo '=== Ensuring vectra database extensions ==='

CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS vector;

\echo '=== Extension setup completed ==='
