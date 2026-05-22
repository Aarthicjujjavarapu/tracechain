"""add span_events table

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-21
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "span_events",
        sa.Column("id",             sa.Integer(),     primary_key=True, autoincrement=True),
        sa.Column("span_id",        sa.String(64),    nullable=False),
        sa.Column("trace_id",       sa.String(64),    nullable=False),
        sa.Column("parent_span_id", sa.String(64),    nullable=True),
        sa.Column("run_id",         sa.String(64),    nullable=True),
        sa.Column("name",           sa.String(255),   nullable=False),
        sa.Column("kind",           sa.String(64),    nullable=False, server_default="step"),
        sa.Column("event_type",     sa.String(64),    nullable=False),
        sa.Column("status",         sa.String(32),    nullable=False, server_default="unset"),
        sa.Column("error_message",  sa.Text(),        nullable=True),
        sa.Column("attributes",     JSONB(),           nullable=True),
        sa.Column("timestamp_ns",   sa.BigInteger(),  nullable=False, server_default="0"),
        sa.Column("duration_ns",    sa.BigInteger(),  nullable=True),
        sa.Column("created_at",     sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_span_events_span_id",  "span_events", ["span_id"])
    op.create_index("ix_span_events_trace_id", "span_events", ["trace_id"])
    op.create_index("ix_span_events_run_id",   "span_events", ["run_id"])
    op.create_index("ix_span_events_parent",   "span_events", ["parent_span_id"])


def downgrade() -> None:
    op.drop_table("span_events")
