"""
Add HNSW index for langchain_pg_embedding

Revision ID: 20251015_01_embedding_hnsw_indexes
Revises: 20251015_00_partition_lc_embeddings
Create Date: 2025-10-15 12:10:00
"""

from __future__ import annotations

from alembic import op
from core.config import get_settings

# revision identifiers, used by Alembic.
revision = '20251015_01_embedding_hnsw_indexes'
down_revision = '20251015_00_partition_lc_embeddings'
branch_labels = None
depends_on = None

APP_SCHEMA = get_settings().app_schema
EMBED_DIM = get_settings().embedding.dim


def upgrade() -> None:
    # Ensure the embedding column keeps the expected fixed dimension before indexing.
    op.execute(
        f"""
DO $$
BEGIN
    IF to_regclass('{APP_SCHEMA}.langchain_pg_embedding') IS NULL THEN
        RAISE NOTICE 'langchain_pg_embedding missing, skipping HNSW index';
        RETURN;
    END IF;

    EXECUTE 'ALTER TABLE {APP_SCHEMA}.langchain_pg_embedding ALTER COLUMN embedding TYPE vector({EMBED_DIM})';
END
$$;
"""
    )

    # Build the cosine HNSW index on the partitioned parent; Postgres will create matching
    # indexes on each partition. CONCURRENTLY is not supported on partitioned parents.
    op.execute(
        f"""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_indexes
                WHERE schemaname = '{APP_SCHEMA}'
                  AND indexname = 'ix_lc_embedding_hnsw_cosine'
            ) THEN
                EXECUTE '
                    CREATE INDEX IF NOT EXISTS ix_lc_embedding_hnsw_cosine
                    ON {APP_SCHEMA}.langchain_pg_embedding
                    USING hnsw (embedding vector_cosine_ops)
                ';
            END IF;
        END
        $$;
        """
    )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(f'DROP INDEX IF EXISTS {APP_SCHEMA}.ix_lc_embedding_hnsw_cosine')
