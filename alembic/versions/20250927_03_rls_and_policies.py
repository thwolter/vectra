"""
Apply RLS and tenant policies to application tables

Revision ID: 20250927_03_rls_and_policies
Revises: 20250927_02_init_schema
Create Date: 2025-09-27 09:22:00
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = '20250927_03_rls_and_policies'
down_revision = '20250927_02_init_schema'
branch_labels = None
depends_on = None

APP_TENANT_TABLES = (
    'documents',
    'upload_jobs',
    'ingestion_versions',
)


_DEF_TEMPLATE = """
DO $$
BEGIN
    IF to_regclass('public.{tbl}') IS NOT NULL THEN
        EXECUTE 'ALTER TABLE public.{tbl} ENABLE ROW LEVEL SECURITY';
        EXECUTE 'ALTER TABLE public.{tbl} FORCE ROW LEVEL SECURITY';
        EXECUTE 'DROP POLICY IF EXISTS tenant_isolation ON public.{tbl}';
        EXECUTE 'CREATE POLICY tenant_isolation ON public.{tbl} USING (tenant_id = NULLIF(current_setting(''app.tenant_id'', true), '''')::uuid) WITH CHECK (tenant_id = NULLIF(current_setting(''app.tenant_id'', true), '''')::uuid)';
    END IF;
END
$$;
"""

_UNDO_TEMPLATE = """
DO $$
BEGIN
    IF to_regclass('public.{tbl}') IS NOT NULL THEN
        EXECUTE 'DROP POLICY IF EXISTS tenant_isolation ON public.{tbl}';
        EXECUTE 'ALTER TABLE public.{tbl} DISABLE ROW LEVEL SECURITY';
    END IF;
END
$$;
"""


def upgrade() -> None:
    # Enable and enforce RLS and create tenant isolation policy on app tables
    for tbl in APP_TENANT_TABLES:
        op.execute(_DEF_TEMPLATE.format(tbl=tbl))


def downgrade() -> None:
    # Drop policy and disable RLS (optional) on app tables
    for tbl in APP_TENANT_TABLES:
        op.execute(_UNDO_TEMPLATE.format(tbl=tbl))
