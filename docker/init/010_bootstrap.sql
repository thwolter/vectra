-- Create logical roles (no login)
\echo '=== Running bootstrap: creating roles and schema ==='

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'ddl_owner') THEN
    CREATE ROLE ddl_owner NOLOGIN;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'vectra_rw') THEN
    CREATE ROLE vectra_rw NOLOGIN;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'vectra_ro') THEN
    CREATE ROLE vectra_ro NOLOGIN;
  END IF;
END$$;

-- Create runtime and migration users
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'vectra_app_user') THEN
    CREATE ROLE vectra_app_user LOGIN PASSWORD 'app-user-password';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'vectra_alembic_user') THEN
    CREATE ROLE vectra_alembic_user LOGIN PASSWORD 'alembic-user-password';
  END IF;
END$$;

-- Memberships
GRANT vectra_rw TO vectra_app_user;
GRANT ddl_owner TO vectra_alembic_user;

-- Dedicated schema owned by ddl_owner
CREATE SCHEMA IF NOT EXISTS vectra AUTHORIZATION ddl_owner;

-- Baseline + default privileges so future objects are usable without Alembic issuing GRANTs
GRANT USAGE ON SCHEMA vectra TO vectra_rw, vectra_ro;

ALTER DEFAULT PRIVILEGES FOR ROLE vectra_alembic_user IN SCHEMA vectra
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO vectra_rw;
ALTER DEFAULT PRIVILEGES FOR ROLE vectra_alembic_user IN SCHEMA vectra
  GRANT SELECT ON TABLES TO vectra_ro;
ALTER DEFAULT PRIVILEGES FOR ROLE vectra_alembic_user IN SCHEMA vectra
  GRANT USAGE, SELECT ON SEQUENCES TO vectra_rw, vectra_ro;
ALTER DEFAULT PRIVILEGES FOR ROLE vectra_alembic_user IN SCHEMA vectra
  GRANT EXECUTE ON FUNCTIONS TO vectra_rw, vectra_ro;

-- Optional: enable pgcrypto for gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS pgcrypto;

\echo '=== Bootstrap completed ==='
