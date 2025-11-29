DO $vectra_users$
DECLARE
    app_user                 text := 'app_user';
    app_password             text := 'app-password';
    alembic_user             text := 'alembic_user';
    alembic_password         text := 'alembic-password';
    pgbouncer_auth_user      text := 'pgbouncer_auth';
    pgbouncer_auth_password  text := convert_from(decode(:'PGBOUNCER_AUTH_PASSWORD_B64', 'base64'), 'UTF8');
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = app_user) THEN
        EXECUTE format('CREATE ROLE %I LOGIN PASSWORD %L', app_user, app_password);
    ELSE
        EXECUTE format('ALTER ROLE %I WITH LOGIN PASSWORD %L', app_user, app_password);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = alembic_user) THEN
        EXECUTE format('CREATE ROLE %I LOGIN PASSWORD %L', alembic_user, alembic_password);
    ELSE
        EXECUTE format('ALTER ROLE %I WITH LOGIN PASSWORD %L', alembic_user, alembic_password);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = pgbouncer_auth_user) THEN
        EXECUTE format('CREATE ROLE %I LOGIN PASSWORD %L', pgbouncer_auth_user, pgbouncer_auth_password);
    ELSE
        EXECUTE format('ALTER ROLE %I WITH LOGIN PASSWORD %L', pgbouncer_auth_user, pgbouncer_auth_password);
    END IF;

    EXECUTE format('GRANT vectra_rw TO %I', app_user);
    EXECUTE format('GRANT ddl_owner TO %I', alembic_user);
END;
$vectra_users$;
