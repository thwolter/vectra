\getenv app_user APP_USER
\getenv app_password APP_PASSWORD
\getenv alembic_user ALEMBIC_USER
\getenv alembic_password ALEMBIC_PASSWORD

SET LOCAL app.app_user         TO :'app_user';
SET LOCAL app.app_password     TO :'app_password';
SET LOCAL app.alembic_user     TO :'alembic_user';
SET LOCAL app.alembic_password TO :'alembic_password';

DO $vectra_users$
DECLARE
    v_app_user         text := COALESCE(current_setting('app.app_user',         true), 'app_user');
    v_app_password     text := COALESCE(current_setting('app.app_password',     true), 'app-password');
    v_alembic_user     text := COALESCE(current_setting('app.alembic_user',     true), 'alembic_user');
    v_alembic_password text := COALESCE(current_setting('app.alembic_password', true), 'alembic-password');
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = v_app_user) THEN
        EXECUTE format('CREATE ROLE %I LOGIN PASSWORD %L', v_app_user, v_app_password);
    ELSE
        EXECUTE format('ALTER ROLE %I WITH LOGIN PASSWORD %L', v_app_user, v_app_password);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = v_alembic_user) THEN
        EXECUTE format('CREATE ROLE %I LOGIN PASSWORD %L', v_alembic_user, v_alembic_password);
    ELSE
        EXECUTE format('ALTER ROLE %I WITH LOGIN PASSWORD %L', v_alembic_user, v_alembic_password);
    END IF;

    EXECUTE format('GRANT vectra_rw TO %I', v_app_user);
    EXECUTE format('GRANT ddl_owner TO %I', v_alembic_user);
END;
$vectra_users$;

COMMIT;
