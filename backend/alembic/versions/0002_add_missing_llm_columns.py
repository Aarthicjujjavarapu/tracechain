"""add missing llm_calls columns

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-21
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE llm_calls
        ADD COLUMN IF NOT EXISTS time_to_first_token_ms INTEGER,
        ADD COLUMN IF NOT EXISTS temperature FLOAT,
        ADD COLUMN IF NOT EXISTS is_stream BOOLEAN NOT NULL DEFAULT FALSE
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE llm_calls
        DROP COLUMN IF EXISTS time_to_first_token_ms,
        DROP COLUMN IF EXISTS temperature
    """)
