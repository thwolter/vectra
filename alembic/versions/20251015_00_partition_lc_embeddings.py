"""
Partition langchain_pg_embedding by tenant_id

Revision ID: 20251015_00_partition_lc_embeddings
Revises: 20251001_00_metis_vector_privs
Create Date: 2025-10-15 12:00:00
"""

from __future__ import annotations

from alembic import op
from core.config import get_settings

# revision identifiers, used by Alembic.
revision = '20251015_00_partition_lc_embeddings'
down_revision = '20251010_00_extend_alembic_version'
branch_labels = None
depends_on = None

APP_SCHEMA = get_settings().db_schema
EMBED_DIM = get_settings().embedding.dim


def upgrade() -> None:
    op.execute(
        f"""
DO $$
DECLARE
    parent regclass := '{APP_SCHEMA}.langchain_pg_embedding'::regclass;
    already_partitioned boolean;
    tenant_rec record;
BEGIN
    IF to_regclass('{APP_SCHEMA}.langchain_pg_embedding') IS NULL THEN
        RAISE NOTICE 'langchain_pg_embedding missing, skipping partition conversion';
        RETURN;
    END IF;

    SELECT EXISTS (SELECT 1 FROM pg_partitioned_table WHERE partrelid = parent)
    INTO already_partitioned;

    IF already_partitioned THEN
        RAISE NOTICE 'langchain_pg_embedding already partitioned, skipping';
        RETURN;
    END IF;

    -- Create a partitioned clone that preserves the FK to langchain_pg_collection and vector dimension.
    EXECUTE format(
        $sql$
        CREATE TABLE {APP_SCHEMA}.langchain_pg_embedding_new (
            id VARCHAR NOT NULL,
            collection_id UUID REFERENCES {APP_SCHEMA}.langchain_pg_collection(uuid) ON DELETE CASCADE,
            embedding vector(%s),
            document VARCHAR NULL,
            cmetadata JSONB NULL,
            tenant_id UUID NOT NULL DEFAULT NULLIF(current_setting('app.tenant_id', true), '')::uuid,
            PRIMARY KEY (tenant_id, id)
        )
        PARTITION BY LIST (tenant_id)
        $sql$,
        {EMBED_DIM}
    );

    -- Ensure we always have a catch-all partition for unexpected tenants.
    EXECUTE 'CREATE TABLE IF NOT EXISTS {APP_SCHEMA}.langchain_pg_embedding_default PARTITION OF {APP_SCHEMA}.langchain_pg_embedding_new DEFAULT';

    -- Create per-tenant partitions for current data.
    PERFORM 1;
    FOR tenant_rec IN (
        SELECT DISTINCT tenant_id
        FROM {APP_SCHEMA}.langchain_pg_embedding
        ORDER BY tenant_id
    )
    LOOP
        EXECUTE format(
            'CREATE TABLE IF NOT EXISTS {APP_SCHEMA}.langchain_pg_embedding_tenant_%s PARTITION OF {APP_SCHEMA}.langchain_pg_embedding_new FOR VALUES IN (%L)',
            replace(tenant_rec.tenant_id::text, '-', '_'),
            tenant_rec.tenant_id
        );
    END LOOP;

    -- Move existing rows into the partitioned table.
    EXECUTE 'INSERT INTO {APP_SCHEMA}.langchain_pg_embedding_new (id, collection_id, embedding, document, cmetadata, tenant_id)
             SELECT id, collection_id, embedding, document, cmetadata, tenant_id
             FROM {APP_SCHEMA}.langchain_pg_embedding';

    -- Swap tables so downstream code keeps using the original name.
    EXECUTE 'ALTER TABLE {APP_SCHEMA}.langchain_pg_embedding RENAME TO langchain_pg_embedding_old';
    EXECUTE 'ALTER TABLE {APP_SCHEMA}.langchain_pg_embedding_new RENAME TO langchain_pg_embedding';

    -- Recreate indexes and RLS on the partitioned parent (applies to all partitions).
    EXECUTE 'CREATE INDEX IF NOT EXISTS ix_cmetadata_gin ON {APP_SCHEMA}.langchain_pg_embedding USING GIN (cmetadata jsonb_path_ops)';
    EXECUTE 'CREATE INDEX IF NOT EXISTS ix_lc_embedding_tenant_collection ON {APP_SCHEMA}.langchain_pg_embedding (tenant_id, collection_id)';

    EXECUTE 'ALTER TABLE {APP_SCHEMA}.langchain_pg_embedding ENABLE ROW LEVEL SECURITY';
    EXECUTE 'ALTER TABLE {APP_SCHEMA}.langchain_pg_embedding FORCE ROW LEVEL SECURITY';
    EXECUTE 'DROP POLICY IF EXISTS tenant_isolation ON {APP_SCHEMA}.langchain_pg_embedding';
    EXECUTE 'CREATE POLICY tenant_isolation ON {APP_SCHEMA}.langchain_pg_embedding USING (tenant_id = NULLIF(current_setting(''app.tenant_id'', true), '''')::uuid) WITH CHECK (tenant_id = NULLIF(current_setting(''app.tenant_id'', true), '''')::uuid)';

    -- Drop the old heap once everything is migrated.
    EXECUTE 'DROP TABLE IF EXISTS {APP_SCHEMA}.langchain_pg_embedding_old CASCADE';
END
$$;
"""
    )


def downgrade() -> None:
    op.execute(
        f"""
DO $$
DECLARE
    is_partitioned boolean;
BEGIN
    IF to_regclass('{APP_SCHEMA}.langchain_pg_embedding') IS NULL THEN
        RETURN;
    END IF;

    SELECT EXISTS (SELECT 1 FROM pg_partitioned_table WHERE partrelid = '{APP_SCHEMA}.langchain_pg_embedding'::regclass)
    INTO is_partitioned;

    IF NOT is_partitioned THEN
        RETURN;
    END IF;

    -- Rebuild a non-partitioned copy to allow rollback.
    CREATE TABLE {APP_SCHEMA}.langchain_pg_embedding_unpartitioned (
        id VARCHAR NOT NULL,
        collection_id UUID REFERENCES {APP_SCHEMA}.langchain_pg_collection(uuid) ON DELETE CASCADE,
        embedding vector({EMBED_DIM}),
        document VARCHAR NULL,
        cmetadata JSONB NULL,
        tenant_id UUID NOT NULL DEFAULT NULLIF(current_setting('app.tenant_id', true), '')::uuid,
        PRIMARY KEY (tenant_id, id)
    );

    INSERT INTO {APP_SCHEMA}.langchain_pg_embedding_unpartitioned (id, collection_id, embedding, document, cmetadata, tenant_id)
    SELECT id, collection_id, embedding, document, cmetadata, tenant_id
    FROM {APP_SCHEMA}.langchain_pg_embedding;

    DROP TABLE IF EXISTS {APP_SCHEMA}.langchain_pg_embedding CASCADE;
    ALTER TABLE {APP_SCHEMA}.langchain_pg_embedding_unpartitioned RENAME TO langchain_pg_embedding;

    CREATE INDEX IF NOT EXISTS ix_cmetadata_gin ON {APP_SCHEMA}.langchain_pg_embedding USING GIN (cmetadata jsonb_path_ops);
    CREATE INDEX IF NOT EXISTS ix_lc_embedding_tenant_collection ON {APP_SCHEMA}.langchain_pg_embedding (tenant_id, collection_id);

    ALTER TABLE {APP_SCHEMA}.langchain_pg_embedding ENABLE ROW LEVEL SECURITY;
    ALTER TABLE {APP_SCHEMA}.langchain_pg_embedding FORCE ROW LEVEL SECURITY;
    DROP POLICY IF EXISTS tenant_isolation ON {APP_SCHEMA}.langchain_pg_embedding;
    CREATE POLICY tenant_isolation ON {APP_SCHEMA}.langchain_pg_embedding USING (tenant_id = NULLIF(current_setting(''app.tenant_id'', true), '''')::uuid) WITH CHECK (tenant_id = NULLIF(current_setting(''app.tenant_id'', true), '''')::uuid);
END
$$;
"""
    )
