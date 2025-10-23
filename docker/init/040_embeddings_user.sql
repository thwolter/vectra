\set ON_ERROR_STOP on

\echo '=== Ensuring embeddings application user exists ==='

\getenv embeddings_user EMBEDDINGS_USER
\if :{?embeddings_user} \else \set embeddings_user 'embeddings_user' \endif

\getenv embeddings_password EMBEDDINGS_PASSWORD
\if :{?embeddings_password} \else \set embeddings_password 'embeddings-password' \endif

BEGIN;
-- Hand off to server-local settings for this transaction
SET LOCAL app.embeddings_user       TO :'embeddings_user';
SET LOCAL app.embeddings_password   TO :'embeddings_password';

DO $embeddings_user$
DECLARE
    embeddings_user     text := current_setting('app.embeddings_user', true);
    embeddings_password text := current_setting('app.embeddings_password', true);
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = embeddings_user) THEN
        EXECUTE format('CREATE ROLE %I LOGIN PASSWORD %L', embeddings_user, embeddings_password);
    ELSE
        EXECUTE format('ALTER ROLE %I WITH LOGIN PASSWORD %L', embeddings_user, embeddings_password);
    END IF;
END;
$embeddings_user$;

COMMIT;

\echo '=== Embeddings application user ready ==='
