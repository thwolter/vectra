"""
ensure vector extension

Revision ID: 20250927_01_ensure_vector
Revises:
Create Date: 2025-09-27 09:05:00
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = '20250927_01_ensure_vector'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    # It's generally safe to keep the extension; no-op downgrade.
    # If you need to drop it, uncomment the next line.
    # op.execute("DROP EXTENSION IF EXISTS vector;")
    pass
