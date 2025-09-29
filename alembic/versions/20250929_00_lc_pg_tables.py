"""
Create LangChain PGVector tables if missing

Revision ID: 20250929_00_lc_pg_tables
Revises: 20250927_03_rls_and_policies
Create Date: 2025-09-29 10:58:00
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = '20250929_00_lc_pg_tables'
down_revision = '20250927_03_rls_and_policies'
branch_labels = None
depends_on = None

# Note: We mirror the schema used by langchain_postgres PGVector backend.
# Tables are only created if they do not already exist to avoid conflicts
# when the vendor library has already initialized them.

_CREATE_COLLECTION = r"""
CREATE TABLE IF NOT EXISTS public.langchain_pg_collection (
    uuid UUID PRIMARY KEY,
    name VARCHAR NOT NULL UNIQUE,
    cmetadata JSON
);
"""

_CREATE_EMBEDDING = r"""
CREATE TABLE IF NOT EXISTS public.langchain_pg_embedding (
    id VARCHAR PRIMARY KEY,
    collection_id UUID REFERENCES public.langchain_pg_collection(uuid) ON DELETE CASCADE,
    embedding vector,
    document VARCHAR NULL,
    cmetadata JSONB NULL
);
"""

_CREATE_GIN_INDEX = r"""
DO $$
BEGIN
    IF to_regclass('public.langchain_pg_embedding') IS NOT NULL THEN
        PERFORM 1 FROM pg_indexes WHERE schemaname='public' AND indexname='ix_cmetadata_gin';
        IF NOT FOUND THEN
            EXECUTE 'CREATE INDEX ix_cmetadata_gin ON public.langchain_pg_embedding USING GIN (cmetadata jsonb_path_ops)';
        END IF;
    END IF;
END
$$;
"""


def upgrade() -> None:
    # Ensure tables exist before applying tenant columns/RLS in subsequent migration
    op.execute(_CREATE_COLLECTION)
    op.execute(_CREATE_EMBEDDING)
    op.execute(_CREATE_GIN_INDEX)


def downgrade() -> None:
    # Drop in reverse order to satisfy FK dependency
    op.execute(
        r"""
        DO $$
        BEGIN
            IF to_regclass('public.langchain_pg_embedding') IS NOT NULL THEN
                EXECUTE 'DROP TABLE public.langchain_pg_embedding';
            END IF;
            IF to_regclass('public.langchain_pg_collection') IS NOT NULL THEN
                EXECUTE 'DROP TABLE public.langchain_pg_collection';
            END IF;
        END
        $$;
        """
    )
