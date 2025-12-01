"""
ensure vector extension

Revision ID: 20250927_01_ensure_vector
Revises:
Create Date: 2025-09-27 09:05:00
"""

from __future__ import annotations

# revision identifiers, used by Alembic.
revision = '20250927_01_ensure_vector'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass
    # Ensure pgvector type is available for downstream tables
    # op.execute('CREATE EXTENSION IF NOT EXISTS vector')


def downgrade() -> None:
    pass
