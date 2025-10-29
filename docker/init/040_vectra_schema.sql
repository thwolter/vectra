
\getenv app_user VECTRA_USER
\getenv alembic_user ALEMBIC_USER
\getenv app_schema VECTRA_SCHEMA

SET LOCAL app.app_schema TO :'app_schema';
SET LOCAL app.app_user TO :'app_user';
SET LOCAL app.alembic_user TO :'alembic_user';

DO
$vectra_schema$
    DECLARE
        v_app_schema       text := COALESCE(current_setting('app.app_schema',       true), 'vectra');
        v_app_user         text := COALESCE(current_setting('app.app_user',         true), 'app_user');
        v_alembic_user     text := COALESCE(current_setting('app.alembic_user',     true), 'alembic_user');
        v_current_db       text := current_database();

    BEGIN
        EXECUTE format('CREATE SCHEMA IF NOT EXISTS %I AUTHORIZATION ddl_owner', v_app_schema);

        EXECUTE format(
                'GRANT USAGE ON SCHEMA %I TO vectra_rw, vectra_ro',
                v_app_schema
                );

        EXECUTE format(
                'ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA %I GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO vectra_rw',
                v_alembic_user,
                v_app_schema
                );

        EXECUTE format(
                'ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA %I GRANT SELECT ON TABLES TO vectra_ro',
                v_alembic_user,
                v_app_schema
                );

        EXECUTE format(
                'ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA %I GRANT USAGE, SELECT ON SEQUENCES TO vectra_rw, vectra_ro',
                v_alembic_user,
                v_app_schema
                );

        EXECUTE format(
                'ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA %I GRANT EXECUTE ON FUNCTIONS TO vectra_rw, vectra_ro',
                v_alembic_user,
                v_app_schema
                );

        EXECUTE format(
                'ALTER ROLE %I IN DATABASE %I SET search_path = %I, public',
                v_app_user,
                v_current_db,
                v_app_schema
                );

        EXECUTE format(
                'ALTER ROLE %I IN DATABASE %I SET search_path = pg_catalog, %I, public',
                v_alembic_user,
                v_current_db,
                v_app_schema
                );

        EXECUTE format('GRANT CREATE ON DATABASE %I TO %I', current_database(), v_alembic_user);
    END;
$vectra_schema$;

COMMIT;
