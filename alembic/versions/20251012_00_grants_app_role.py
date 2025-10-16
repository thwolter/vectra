"""
Grant application role privileges on vecapi schema and tables

Revision ID: 20251012_00_grants_app_role
Revises: 20250929_01_vec_tenant_rls
Create Date: 2025-10-12 12:50:00
"""

from __future__ import annotations

import os
import re
from typing import Final

from alembic import op

# revision identifiers, used by Alembic.
revision: Final[str] = '20251012_00_grants_app_role'
down_revision: Final[str] = '20250929_01_vec_tenant_rls'
branch_labels = None
depends_on = None

APP_SCHEMA: Final[str] = 'vecapi'
APP_ROLE: Final[str] = 'vectra_rw'


def upgrade() -> None:
    op.execute(
        f"""
        DO $$
        DECLARE
            rname text := '{APP_ROLE}';
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = rname) THEN
                EXECUTE format('CREATE ROLE %I NOLOGIN INHERIT NOBYPASSRLS', rname);
            END IF;
        END;
        $$;
        """
    )

    # Ensure schema exists (no-op if already created by prior migration)
    op.execute(f'CREATE SCHEMA IF NOT EXISTS {APP_SCHEMA}')

    # Grant schema usage
    op.execute(f'GRANT USAGE ON SCHEMA {APP_SCHEMA} TO {APP_ROLE}')

    # Grant DML on all existing tables in schema and default privileges for future tables
    op.execute(f'GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA {APP_SCHEMA} TO {APP_ROLE}')
    op.execute(
        f'ALTER DEFAULT PRIVILEGES IN SCHEMA {APP_SCHEMA} GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {APP_ROLE}'
    )

    # Grant sequence usage if any
    op.execute(f'GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA {APP_SCHEMA} TO {APP_ROLE}')
    op.execute(
        f'ALTER DEFAULT PRIVILEGES IN SCHEMA {APP_SCHEMA} GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO {APP_ROLE}'
    )


def downgrade() -> None:  # pragma: no cover - safe to leave grants in place on downgrade
    # Intentionally a no-op: revoking privileges automatically on downgrade is risky
    # and environment-specific. Leaving grants in place is safer for local/test envs.
    return None
