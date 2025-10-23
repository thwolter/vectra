\set ON_ERROR_STOP on

\echo '=== Configuring embeddings permissions ==='

\getenv embeddings_user EMBEDDINGS_USER
\if :{?embeddings_user} \else \set embeddings_user 'embeddings_user' \endif

DO $embeddings_roles$
    BEGIN
      IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'embedding_rw') THEN
        EXECUTE 'CREATE ROLE embedding_rw NOLOGIN';
      END IF;
    END;
$embeddings_roles$;

BEGIN;
SET LOCAL app.embeddings_user TO :'embeddings_user';

DO $embeddings_permissions$
DECLARE
  embeddings_user text := current_setting('app.embeddings_user', true);
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = embeddings_user) THEN
    RAISE EXCEPTION 'Role % does not exist. Run 040_embeddings_user.sql first.', embeddings_user;
  END IF;

  EXECUTE format('GRANT embedding_rw TO %I', embeddings_user);
END;
$embeddings_permissions$;

COMMIT;

\echo '=== Embeddings permissions configured ==='
