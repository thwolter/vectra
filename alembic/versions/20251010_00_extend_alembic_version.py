"""
Widen alembic_version.version_num for longer revision ids

Revision ID: 20251010_00_extend_alembic_version
Revises: 20251001_00_metis_vector_privs
Create Date: 2025-10-10 08:00:00
"""

from __future__ import annotations

from alembic import op
from core.config import get_settings

# revision identifiers, used by Alembic.
revision = '20251010_00_extend_alembic_version'
down_revision = '20250929_01_vec_tenant_rls'
branch_labels = None
depends_on = None

APP_SCHEMA = get_settings().app_schema


def upgrade() -> None:
    op.execute(
        f"""
        ALTER TABLE {APP_SCHEMA}.alembic_version
        ALTER COLUMN version_num TYPE varchar(64);
        """
    )


def downgrade() -> None:
    op.execute(
        f"""
        ALTER TABLE {APP_SCHEMA}.alembic_version
        ALTER COLUMN version_num TYPE varchar(32);
        """
    )
