\set ON_ERROR_STOP on

DO $vectra_roles$
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
END;
$vectra_roles$;
