\set ON_ERROR_STOP on


\getenv app_user VECTRA_USER
\if :{?app_user} \else \set app_user 'vectra_user' \endif

\getenv alembic_user ALEMBIC_USER
\if :{?alembic_user} \else \set alembic_user 'alembic_user' \endif

\getenv app_schema VECTRA_SCHEMA
\if :{?app_schema} \else \set app_schema 'vectra' \endif

BEGIN;
-- Hand off to server-local settings for this transaction
SET LOCAL app.app_schema TO :'app_schema';
SET LOCAL app.app_user TO :'app_user';
SET LOCAL app.alembic_user TO :'alembic_user';

DO
$vectra_schema$
    DECLARE
        app_schema   text := current_setting('app.app_schema', true);
        app_user     text := current_setting('app.app_user', true);
        alembic_user text := current_setting('app.alembic_user', true);
        current_db   text := current_database();
    BEGIN
        EXECUTE format('CREATE SCHEMA IF NOT EXISTS %I AUTHORIZATION ddl_owner', app_schema);

        EXECUTE format(
                'GRANT USAGE ON SCHEMA %I TO vectra_rw, vectra_ro',
                app_schema
                );

        EXECUTE format(
                'ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA %I GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO vectra_rw',
                alembic_user,
                app_schema
                );

        EXECUTE format(
                'ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA %I GRANT SELECT ON TABLES TO vectra_ro',
                alembic_user,
                app_schema
                );

        EXECUTE format(
                'ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA %I GRANT USAGE, SELECT ON SEQUENCES TO vectra_rw, vectra_ro',
                alembic_user,
                app_schema
                );

        EXECUTE format(
                'ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA %I GRANT EXECUTE ON FUNCTIONS TO vectra_rw, vectra_ro',
                alembic_user,
                app_schema
                );

        EXECUTE format(
                'ALTER ROLE %I IN DATABASE %I SET search_path = %I, public',
                app_user,
                current_db,
                app_schema
                );

        EXECUTE format(
                'ALTER ROLE %I IN DATABASE %I SET search_path = pg_catalog, %I, public',
                alembic_user,
                current_db,
                app_schema
                );

        EXECUTE format('GRANT CREATE ON DATABASE %I TO %I', current_database(), alembic_user);
    END;
$vectra_schema$;

COMMIT;

