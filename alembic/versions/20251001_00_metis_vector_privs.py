"""
Grant Metis role access to LangChain vector tables

Revision ID: 20251001_00_metis_vector_privs
Revises: 20250929_01_vec_tenant_rls
Create Date: 2025-10-01 08:00:00
"""

from __future__ import annotations

from alembic import op
from app.core.db_schema import APP_SCHEMA

# revision identifiers, used by Alembic.
revision = '20251001_00_metis_vector_privs'
down_revision = '20250929_01_vec_tenant_rls'
branch_labels = None
depends_on = None

_GRANT_METIS_ACCESS = f"""
DO $$
DECLARE
    schema_name constant text := '{APP_SCHEMA}';
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'metis_rw') THEN
        EXECUTE format('GRANT USAGE ON SCHEMA %I TO metis_rw', schema_name);

        IF to_regclass(format('%I.langchain_pg_collection', schema_name)) IS NOT NULL THEN
            EXECUTE format('GRANT SELECT ON %I.langchain_pg_collection TO metis_rw', schema_name);
        END IF;

        IF to_regclass(format('%I.langchain_pg_embedding', schema_name)) IS NOT NULL THEN
            EXECUTE format('GRANT SELECT ON %I.langchain_pg_embedding TO metis_rw', schema_name);
            EXECUTE format('REVOKE UPDATE ON %I.langchain_pg_embedding FROM metis_rw', schema_name);

            IF EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = schema_name AND table_name = 'langchain_pg_embedding' AND column_name = 'cmetadata'
            ) THEN
                EXECUTE format('GRANT UPDATE (cmetadata) ON %I.langchain_pg_embedding TO metis_rw', schema_name);
            END IF;

            IF EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = schema_name AND table_name = 'langchain_pg_embedding' AND column_name = 'updated_at'
            ) THEN
                EXECUTE format('GRANT UPDATE (updated_at) ON %I.langchain_pg_embedding TO metis_rw', schema_name);
            END IF;
        END IF;
    END IF;
END
$$;
"""

_REVOKE_METIS_ACCESS = f"""
DO $$
DECLARE
    schema_name constant text := '{APP_SCHEMA}';
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'metis_rw') THEN
        IF to_regclass(format('%I.langchain_pg_embedding', schema_name)) IS NOT NULL THEN
            IF EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = schema_name AND table_name = 'langchain_pg_embedding' AND column_name = 'updated_at'
            ) THEN
                EXECUTE format('REVOKE UPDATE (updated_at) ON %I.langchain_pg_embedding FROM metis_rw', schema_name);
            END IF;

            IF EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = schema_name AND table_name = 'langchain_pg_embedding' AND column_name = 'cmetadata'
            ) THEN
                EXECUTE format('REVOKE UPDATE (cmetadata) ON %I.langchain_pg_embedding FROM metis_rw', schema_name);
            END IF;

            EXECUTE format('REVOKE SELECT ON %I.langchain_pg_embedding FROM metis_rw', schema_name);
        END IF;

        IF to_regclass(format('%I.langchain_pg_collection', schema_name)) IS NOT NULL THEN
            EXECUTE format('REVOKE SELECT ON %I.langchain_pg_collection FROM metis_rw', schema_name);
        END IF;

        EXECUTE format('REVOKE USAGE ON SCHEMA %I FROM metis_rw', schema_name);
    END IF;
END
$$;
"""


def upgrade() -> None:
    op.execute(_GRANT_METIS_ACCESS)


def downgrade() -> None:
    op.execute(_REVOKE_METIS_ACCESS)
