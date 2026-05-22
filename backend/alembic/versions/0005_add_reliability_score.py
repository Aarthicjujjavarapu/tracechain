"""add reliability_score to workflow_runs

Revision ID: 0005
Revises: 0004
Create Date: 2026-05-21
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("workflow_runs", sa.Column("reliability_score",   sa.Integer(), nullable=True))
    op.add_column("workflow_runs", sa.Column("reliability_reasons", JSONB(),      nullable=True))


def downgrade() -> None:
    op.drop_column("workflow_runs", "reliability_reasons")
    op.drop_column("workflow_runs", "reliability_score")
