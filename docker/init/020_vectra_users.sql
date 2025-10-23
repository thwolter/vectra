\set ON_ERROR_STOP on

\echo '=== Ensuring vectra application users exist ==='

\getenv app_user VECTRA_USER
\if :{?app_user} \else \set app_user 'vectra_user' \endif

\getenv app_password VECTRA_PASSWORD
\if :{?app_password} \else \set app_password 'vectra-password' \endif

\getenv alembic_user ALEMBIC_USER
\if :{?alembic_user} \else \set alembic_user 'alembic_user' \endif

\getenv alembic_password ALEMBIC_PASSWORD
\if :{?alembic_password} \else \set alembic_password 'alembic-password' \endif

BEGIN;
-- Hand off values to the server (visible to this txn)
SET LOCAL app.app_user        TO :'app_user';
SET LOCAL app.app_password    TO :'app_password';
SET LOCAL app.alembic_user    TO :'alembic_user';
SET LOCAL app.alembic_password TO :'alembic_password';

DO $vectra_users$
DECLARE
    app_user         text := current_setting('app.app_user');
    app_password     text := current_setting('app.app_password');
    alembic_user     text := current_setting('app.alembic_user');
    alembic_password text := current_setting('app.alembic_password');
BEGIN
    -- Create the application user if it doesn't exist
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = app_user) THEN
        EXECUTE format('CREATE ROLE %I LOGIN PASSWORD %L', app_user, app_password);
    ELSE
        EXECUTE format('ALTER ROLE %I WITH LOGIN PASSWORD %L', app_user, app_password);
    END IF;

    -- Create the alembic user if it doesn't exist
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = alembic_user) THEN
        EXECUTE format('CREATE ROLE %I LOGIN PASSWORD %L', alembic_user, alembic_password);
    ELSE
        EXECUTE format('ALTER ROLE %I WITH LOGIN PASSWORD %L', alembic_user, alembic_password);
    END IF;

    EXECUTE format('GRANT vectra_rw TO %I', app_user);
    EXECUTE format('GRANT ddl_owner TO %I', alembic_user);
END;
$vectra_users$;

COMMIT;

\echo '=== Vectra application users ready ==='
