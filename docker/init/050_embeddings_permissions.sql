\set ON_ERROR_STOP on

\getenv embeddings_user EMBEDDINGS_USER
\if :{?embeddings_user} \else \set embeddings_user 'embeddings_user' \endif

DO $embeddings_roles$
    BEGIN
      IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'embedding_rw') THEN
        EXECUTE 'CREATE ROLE embedding_rw NOLOGIN';
      END IF;
    END;
$embeddings_roles$;

