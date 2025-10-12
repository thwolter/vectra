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
revision: Final[str] = "20251012_00_grants_app_role"
down_revision: Final[str] = "20250929_01_vec_tenant_rls"
branch_labels = None
depends_on = None

APP_SCHEMA: Final[str] = "vecapi"


def _derive_app_role() -> str:
    """Derive the application DB role to grant privileges to.

    Order of precedence:
    1) APP_DB_USER env var if provided
    2) Username parsed from POSTGRES_URL env var
    3) Fallback to 'vecapi_app'
    """
    explicit = os.getenv("APP_DB_USER")
    if explicit:
        return explicit

    pg_url = os.getenv("POSTGRES_URL") or os.getenv("DATABASE_URL")
    if pg_url:
        # crude parse: scheme://user:pass@host/db
        m = re.match(r"^[a-z+]+://([^:@/]+)", pg_url)
        if m:
            return m.group(1)
    return "vecapi_app"


def upgrade() -> None:
    role = _derive_app_role()
    # Quote role name in case it contains special chars
    quoted_role = '"' + role.replace('"', '""') + '"'

    # Ensure schema exists (no-op if already created by prior migration)
    op.execute(f"CREATE SCHEMA IF NOT EXISTS {APP_SCHEMA}")

    # Grant schema usage
    op.execute(f"GRANT USAGE ON SCHEMA {APP_SCHEMA} TO {quoted_role}")

    # Grant DML on all existing tables in schema and default privileges for future tables
    op.execute(
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA {APP_SCHEMA} TO {quoted_role}"
    )
    op.execute(
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA {APP_SCHEMA} GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {quoted_role}"
    )

    # Grant sequence usage if any
    op.execute(f"GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA {APP_SCHEMA} TO {quoted_role}")
    op.execute(
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA {APP_SCHEMA} GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO {quoted_role}"
    )


def downgrade() -> None:  # pragma: no cover - safe to leave grants in place on downgrade
    # Intentionally a no-op: revoking privileges automatically on downgrade is risky
    # and environment-specific. Leaving grants in place is safer for local/test envs.
    return None
