import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Text, Boolean, Integer, Float,
    DateTime, ForeignKey, Enum as SAEnum
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
import enum

from .database import Base


def _uuid():
    return str(uuid.uuid4())


def _now():
    return datetime.now(timezone.utc)


# ─── Enums ────────────────────────────────────────────────────────────────────

class RunStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    success = "success"
    failed  = "failed"


class StepType(str, enum.Enum):
    step     = "step"
    llm_step = "llm_step"


class LLMStatus(str, enum.Enum):
    success = "success"
    failed  = "failed"


# ─── Models ───────────────────────────────────────────────────────────────────

class WorkflowRun(Base):
    __tablename__ = "workflow_runs"

    id              = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    workflow_name   = Column(String(255), nullable=False, index=True)
    status          = Column(SAEnum(RunStatus), nullable=False, default=RunStatus.pending)
    input_payload   = Column(JSONB, nullable=False, default=dict)
    output_payload  = Column(JSONB, nullable=True)
    error_message   = Column(Text, nullable=True)
    started_at      = Column(DateTime(timezone=True), nullable=False, default=_now)
    ended_at        = Column(DateTime(timezone=True), nullable=True)
    duration_ms     = Column(Integer, nullable=True)
    total_cost      = Column(Float, nullable=True)
    total_tokens    = Column(Integer, nullable=True)
    original_run_id = Column(UUID(as_uuid=False), ForeignKey("workflow_runs.id"), nullable=True)
    is_replay       = Column(Boolean, nullable=False, default=False)
    metadata_       = Column("metadata", JSONB, nullable=True)

    steps      = relationship("TraceStep", back_populates="run", cascade="all, delete-orphan")
    llm_calls  = relationship("LLMCall", back_populates="run", cascade="all, delete-orphan")
    evaluations = relationship("EvaluationResult", back_populates="run", cascade="all, delete-orphan")
    feedback   = relationship("HumanFeedback", back_populates="run", cascade="all, delete-orphan")


class TraceStep(Base):
    __tablename__ = "trace_steps"

    id             = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    run_id         = Column(UUID(as_uuid=False), ForeignKey("workflow_runs.id"), nullable=False, index=True)
    step_name      = Column(String(255), nullable=False)
    step_type      = Column(SAEnum(StepType), nullable=False, default=StepType.step)
    status         = Column(SAEnum(RunStatus), nullable=False, default=RunStatus.pending)
    input_payload  = Column(JSONB, nullable=False, default=dict)
    output_payload = Column(JSONB, nullable=True)
    error_message  = Column(Text, nullable=True)
    started_at     = Column(DateTime(timezone=True), nullable=False, default=_now)
    ended_at       = Column(DateTime(timezone=True), nullable=True)
    duration_ms    = Column(Integer, nullable=True)
    retry_count    = Column(Integer, nullable=False, default=0)
    metadata_      = Column("metadata", JSONB, nullable=True)

    run       = relationship("WorkflowRun", back_populates="steps")
    llm_calls = relationship("LLMCall", back_populates="step", cascade="all, delete-orphan")


class LLMCall(Base):
    __tablename__ = "llm_calls"

    id             = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    run_id         = Column(UUID(as_uuid=False), ForeignKey("workflow_runs.id"), nullable=False, index=True)
    step_id        = Column(UUID(as_uuid=False), ForeignKey("trace_steps.id"), nullable=True)
    provider       = Column(String(100), nullable=False, default="openai")
    model          = Column(String(100), nullable=False)
    prompt         = Column(Text, nullable=False)
    response       = Column(Text, nullable=True)
    input_tokens   = Column(Integer, nullable=True)
    output_tokens  = Column(Integer, nullable=True)
    total_tokens   = Column(Integer, nullable=True)
    estimated_cost = Column(Float, nullable=True)
    latency_ms              = Column(Integer, nullable=True)
    time_to_first_token_ms  = Column(Integer, nullable=True)
    is_stream               = Column(Boolean, nullable=False, default=False)
    temperature             = Column(Float, nullable=True)
    status                  = Column(SAEnum(LLMStatus), nullable=False, default=LLMStatus.success)
    error_message           = Column(Text, nullable=True)
    prompt_version          = Column(String(50), nullable=True)
    created_at              = Column(DateTime(timezone=True), nullable=False, default=_now)

    run  = relationship("WorkflowRun", back_populates="llm_calls")
    step = relationship("TraceStep", back_populates="llm_calls")


class PromptVersion(Base):
    __tablename__ = "prompt_versions"

    id          = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    prompt_name = Column(String(255), nullable=False, index=True)
    version     = Column(String(50), nullable=False)
    prompt_text = Column(Text, nullable=False)
    is_active   = Column(Boolean, nullable=False, default=True)
    metadata_   = Column("metadata", JSONB, nullable=True)
    created_at  = Column(DateTime(timezone=True), nullable=False, default=_now)


class EvaluationResult(Base):
    __tablename__ = "evaluation_results"

    id                 = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    run_id             = Column(UUID(as_uuid=False), ForeignKey("workflow_runs.id"), nullable=False, index=True)
    relevance_score    = Column(Float, nullable=False, default=0.0)
    groundedness_score = Column(Float, nullable=False, default=0.0)
    hallucination_risk = Column(Float, nullable=False, default=0.0)
    quality_score      = Column(Float, nullable=False, default=0.0)
    failure_reason     = Column(Text, nullable=True)
    created_at         = Column(DateTime(timezone=True), nullable=False, default=_now)

    run = relationship("WorkflowRun", back_populates="evaluations")


class HumanFeedback(Base):
    __tablename__ = "human_feedback"

    id         = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    run_id     = Column(UUID(as_uuid=False), ForeignKey("workflow_runs.id"), nullable=False, index=True)
    rating     = Column(Integer, nullable=False)
    comment    = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)

    run = relationship("WorkflowRun", back_populates="feedback")
