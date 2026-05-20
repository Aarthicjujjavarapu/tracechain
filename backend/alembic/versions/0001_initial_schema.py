"""initial schema

Revision ID: 0001
Revises:
Create Date: 2024-01-01 00:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "workflow_runs",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("workflow_name", sa.String(255), nullable=False),
        sa.Column("status", sa.Enum("pending", "running", "success", "failed", name="runstatus"), nullable=False, server_default="pending"),
        sa.Column("input_payload", JSONB, nullable=False, server_default="{}"),
        sa.Column("output_payload", JSONB, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer, nullable=True),
        sa.Column("total_cost", sa.Float, nullable=True),
        sa.Column("total_tokens", sa.Integer, nullable=True),
        sa.Column("original_run_id", UUID(as_uuid=False), sa.ForeignKey("workflow_runs.id"), nullable=True),
        sa.Column("is_replay", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("metadata", JSONB, nullable=True),
    )
    op.create_index("ix_workflow_runs_workflow_name", "workflow_runs", ["workflow_name"])

    op.create_table(
        "trace_steps",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("run_id", UUID(as_uuid=False), sa.ForeignKey("workflow_runs.id"), nullable=False),
        sa.Column("step_name", sa.String(255), nullable=False),
        sa.Column("step_type", sa.Enum("step", "llm_step", name="steptype"), nullable=False, server_default="step"),
        sa.Column("status", sa.Enum("pending", "running", "success", "failed", name="runstatus"), nullable=False, server_default="pending"),
        sa.Column("input_payload", JSONB, nullable=False, server_default="{}"),
        sa.Column("output_payload", JSONB, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer, nullable=True),
        sa.Column("retry_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("metadata", JSONB, nullable=True),
    )
    op.create_index("ix_trace_steps_run_id", "trace_steps", ["run_id"])

    op.create_table(
        "llm_calls",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("run_id", UUID(as_uuid=False), sa.ForeignKey("workflow_runs.id"), nullable=False),
        sa.Column("step_id", UUID(as_uuid=False), sa.ForeignKey("trace_steps.id"), nullable=True),
        sa.Column("provider", sa.String(100), nullable=False, server_default="openai"),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("prompt", sa.Text, nullable=False),
        sa.Column("response", sa.Text, nullable=True),
        sa.Column("input_tokens", sa.Integer, nullable=True),
        sa.Column("output_tokens", sa.Integer, nullable=True),
        sa.Column("total_tokens", sa.Integer, nullable=True),
        sa.Column("estimated_cost", sa.Float, nullable=True),
        sa.Column("latency_ms", sa.Integer, nullable=True),
        sa.Column("temperature", sa.Float, nullable=True),
        sa.Column("status", sa.Enum("success", "failed", name="llmstatus"), nullable=False, server_default="success"),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("prompt_version", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_llm_calls_run_id", "llm_calls", ["run_id"])

    op.create_table(
        "prompt_versions",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("prompt_name", sa.String(255), nullable=False),
        sa.Column("version", sa.String(50), nullable=False),
        sa.Column("prompt_text", sa.Text, nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("metadata", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_prompt_versions_prompt_name", "prompt_versions", ["prompt_name"])

    op.create_table(
        "evaluation_results",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("run_id", UUID(as_uuid=False), sa.ForeignKey("workflow_runs.id"), nullable=False),
        sa.Column("relevance_score", sa.Float, nullable=False, server_default="0"),
        sa.Column("groundedness_score", sa.Float, nullable=False, server_default="0"),
        sa.Column("hallucination_risk", sa.Float, nullable=False, server_default="0"),
        sa.Column("quality_score", sa.Float, nullable=False, server_default="0"),
        sa.Column("failure_reason", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_evaluation_results_run_id", "evaluation_results", ["run_id"])

    op.create_table(
        "human_feedback",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("run_id", UUID(as_uuid=False), sa.ForeignKey("workflow_runs.id"), nullable=False),
        sa.Column("rating", sa.Integer, nullable=False),
        sa.Column("comment", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_human_feedback_run_id", "human_feedback", ["run_id"])


def downgrade() -> None:
    op.drop_table("human_feedback")
    op.drop_table("evaluation_results")
    op.drop_table("prompt_versions")
    op.drop_table("llm_calls")
    op.drop_table("trace_steps")
    op.drop_table("workflow_runs")
    op.execute("DROP TYPE IF EXISTS runstatus")
    op.execute("DROP TYPE IF EXISTS steptype")
    op.execute("DROP TYPE IF EXISTS llmstatus")
