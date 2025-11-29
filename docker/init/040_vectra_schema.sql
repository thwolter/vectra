DO
$vectra_schema$
    DECLARE
        app_schema       text := 'vectra';
        vectra_user         text := 'vectra_user';
        alembic_user     text := 'alembic_user';
        current_db       text := current_database();

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
                vectra_user,
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
