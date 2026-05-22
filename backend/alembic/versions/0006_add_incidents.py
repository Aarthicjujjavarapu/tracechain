"""add incidents and incident_runs tables

Revision ID: 0006
Revises: 0005
Create Date: 2026-05-21
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "incidents",
        sa.Column("id",                 UUID(as_uuid=False), primary_key=True),
        sa.Column("title",              sa.String(255), nullable=False),
        sa.Column("category",           sa.String(64),  nullable=False),
        sa.Column("severity",           sa.String(16),  nullable=False, server_default="MEDIUM"),
        sa.Column("status",             sa.String(16),  nullable=False, server_default="OPEN"),
        sa.Column("workflow_name",      sa.String(255), nullable=True),
        sa.Column("occurrence_count",   sa.Integer(),   nullable=False, server_default="1"),
        sa.Column("first_seen_at",      sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_seen_at",       sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("evidence",           JSONB(),         nullable=True),
        sa.Column("recommended_action", sa.Text(),       nullable=True),
        sa.Column("resolved_at",        sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at",         sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_incidents_category",      "incidents", ["category"])
    op.create_index("ix_incidents_status",        "incidents", ["status"])
    op.create_index("ix_incidents_workflow_name", "incidents", ["workflow_name"])

    op.create_table(
        "incident_runs",
        sa.Column("incident_id", UUID(as_uuid=False), sa.ForeignKey("incidents.id",       ondelete="CASCADE"), nullable=False),
        sa.Column("run_id",      UUID(as_uuid=False), sa.ForeignKey("workflow_runs.id",    ondelete="CASCADE"), nullable=False),
        sa.Column("linked_at",   sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("incident_id", "run_id"),
    )
    op.create_index("ix_incident_runs_run_id", "incident_runs", ["run_id"])


def downgrade() -> None:
    op.drop_table("incident_runs")
    op.drop_table("incidents")
