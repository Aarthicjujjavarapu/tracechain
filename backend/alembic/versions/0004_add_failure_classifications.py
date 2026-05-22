"""add failure_classifications table

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-21
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "failure_classifications",
        sa.Column("id",             UUID(as_uuid=False), primary_key=True),
        sa.Column("run_id",         UUID(as_uuid=False), sa.ForeignKey("workflow_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("step_id",        UUID(as_uuid=False), nullable=True),
        sa.Column("category",       sa.String(64),  nullable=False),
        sa.Column("severity",       sa.String(16),  nullable=False, server_default="MEDIUM"),
        sa.Column("evidence",       JSONB(),         nullable=True),
        sa.Column("recommendation", sa.Text(),       nullable=True),
        sa.Column("created_at",     sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_failure_classifications_run_id",   "failure_classifications", ["run_id"])
    op.create_index("ix_failure_classifications_category", "failure_classifications", ["category"])


def downgrade() -> None:
    op.drop_table("failure_classifications")
