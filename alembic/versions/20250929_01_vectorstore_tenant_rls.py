"""
Add tenant_id and RLS to LangChain PGVector tables

Revision ID: 20250929_01_vec_tenant_rls
Revises: 20250927_03_rls_and_policies
Create Date: 2025-09-29 10:46:00
"""

from __future__ import annotations

from alembic import op

APP_SCHEMA = 'vecapi'

# revision identifiers, used by Alembic.
revision = '20250929_01_vec_tenant_rls'
down_revision = '20250929_00_lc_pg_tables'
branch_labels = None
depends_on = None


_ADD_TENANT_COL_TEMPLATE = """
DO $$
BEGIN
    IF to_regclass('{schema}.{tbl}') IS NOT NULL THEN
        -- Add tenant_id column with default from app.tenant_id; make NOT NULL
        EXECUTE 'ALTER TABLE {schema}.{tbl} ADD COLUMN IF NOT EXISTS tenant_id uuid';
        EXECUTE 'ALTER TABLE {schema}.{tbl} ALTER COLUMN tenant_id SET DEFAULT NULLIF(current_setting(''app.tenant_id'', true), '''')::uuid';
        -- Backfill any existing rows to a sentinel tenant if NULL
        EXECUTE 'UPDATE {schema}.{tbl} SET tenant_id = COALESCE(tenant_id, ''00000000-0000-0000-0000-000000000000''::uuid)';
        EXECUTE 'ALTER TABLE {schema}.{tbl} ALTER COLUMN tenant_id SET NOT NULL';
    END IF;
END
$$;
"""

_ADD_INDEX_TEMPLATE = """
DO $$
BEGIN
    IF to_regclass('{schema}.{tbl}') IS NOT NULL THEN
        {stmts}
    END IF;
END
$$;
"""

_ENABLE_RLS_TEMPLATE = """
DO $$
BEGIN
    IF to_regclass('{schema}.{tbl}') IS NOT NULL THEN
        EXECUTE 'ALTER TABLE {schema}.{tbl} ENABLE ROW LEVEL SECURITY';
        EXECUTE 'ALTER TABLE {schema}.{tbl} FORCE ROW LEVEL SECURITY';
        EXECUTE 'DROP POLICY IF EXISTS tenant_isolation ON {schema}.{tbl}';
        EXECUTE 'CREATE POLICY tenant_isolation ON {schema}.{tbl} USING (tenant_id = NULLIF(current_setting(''app.tenant_id'', true), '''')::uuid) WITH CHECK (tenant_id = NULLIF(current_setting(''app.tenant_id'', true), '''')::uuid)';
    END IF;
END
$$;
"""

_DISABLE_RLS_TEMPLATE = """
DO $$
BEGIN
    IF to_regclass('{schema}.{tbl}') IS NOT NULL THEN
        EXECUTE 'DROP POLICY IF EXISTS tenant_isolation ON {schema}.{tbl}';
        EXECUTE 'ALTER TABLE {schema}.{tbl} DISABLE ROW LEVEL SECURITY';
    END IF;
END
$$;
"""

_DROP_INDEX_TEMPLATE = """
DO $$
BEGIN
    IF to_regclass('{schema}.{tbl}') IS NOT NULL THEN
        {stmts}
    END IF;
END
$$;
"""


def upgrade() -> None:
    # Ensure tenant_id column exists and is populated
    for tbl in ('langchain_pg_collection', 'langchain_pg_embedding'):
        op.execute(_ADD_TENANT_COL_TEMPLATE.format(schema=APP_SCHEMA, tbl=tbl))

    # Indexes to support tenant-scoped lookups
    op.execute(
        _ADD_INDEX_TEMPLATE.format(
            schema=APP_SCHEMA,
            tbl='langchain_pg_collection',
            stmts="""
                PERFORM 1 FROM pg_indexes WHERE schemaname = '{schema}' AND indexname = 'ix_lc_collection_tenant_name';
                IF NOT FOUND THEN
                    EXECUTE 'CREATE INDEX ix_lc_collection_tenant_name ON {schema}.langchain_pg_collection (tenant_id, name)';
                END IF;
            """.format(schema=APP_SCHEMA),
        )
    )
    op.execute(
        _ADD_INDEX_TEMPLATE.format(
            schema=APP_SCHEMA,
            tbl='langchain_pg_embedding',
            stmts="""
                PERFORM 1 FROM pg_indexes WHERE schemaname = '{schema}' AND indexname = 'ix_lc_embedding_tenant_collection';
                IF NOT FOUND THEN
                    EXECUTE 'CREATE INDEX ix_lc_embedding_tenant_collection ON {schema}.langchain_pg_embedding (tenant_id, collection_id)';
                END IF;
            """.format(schema=APP_SCHEMA),
        )
    )

    # Enable and enforce RLS with tenant policy
    for tbl in ('langchain_pg_collection', 'langchain_pg_embedding'):
        op.execute(_ENABLE_RLS_TEMPLATE.format(schema=APP_SCHEMA, tbl=tbl))


def downgrade() -> None:
    # Drop RLS policies and disable RLS
    for tbl in ('langchain_pg_collection', 'langchain_pg_embedding'):
        op.execute(_DISABLE_RLS_TEMPLATE.format(schema=APP_SCHEMA, tbl=tbl))

    # Drop indexes if exist
    op.execute(
        _DROP_INDEX_TEMPLATE.format(
            schema=APP_SCHEMA,
            tbl='langchain_pg_embedding',
            stmts="""
                IF to_regclass('{schema}.ix_lc_embedding_tenant_collection') IS NOT NULL THEN
                    EXECUTE 'DROP INDEX {schema}.ix_lc_embedding_tenant_collection';
                END IF;
            """.format(schema=APP_SCHEMA),
        )
    )
    op.execute(
        _DROP_INDEX_TEMPLATE.format(
            schema=APP_SCHEMA,
            tbl='langchain_pg_collection',
            stmts="""
                IF to_regclass('{schema}.ix_lc_collection_tenant_name') IS NOT NULL THEN
                    EXECUTE 'DROP INDEX {schema}.ix_lc_collection_tenant_name';
                END IF;
            """.format(schema=APP_SCHEMA),
        )
    )

    # Drop tenant_id columns (if exist)
    for tbl in ('langchain_pg_embedding', 'langchain_pg_collection'):
        op.execute(
            """
            DO $$
            BEGIN
                IF to_regclass('{{schema}}.{tbl}') IS NOT NULL THEN
                    IF EXISTS (
                        SELECT 1
                        FROM information_schema.columns
                        WHERE table_schema = '{{schema}}' AND table_name = '{tbl}' AND column_name = 'tenant_id'
                    ) THEN
                        EXECUTE 'ALTER TABLE {{schema}}.{tbl} DROP COLUMN tenant_id';
                    END IF;
                END IF;
            END
            $$;
            """.format(tbl=tbl)
        )
