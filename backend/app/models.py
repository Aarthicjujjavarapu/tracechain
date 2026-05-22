import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Text, Boolean, Integer, Float, BigInteger,
    DateTime, ForeignKey, Enum as SAEnum, Table
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


class FailureCategory(str, enum.Enum):
    RETRIEVAL_FAILURE    = "RETRIEVAL_FAILURE"
    LOW_RELEVANCE_CONTEXT = "LOW_RELEVANCE_CONTEXT"
    CONTEXT_WINDOW_RISK  = "CONTEXT_WINDOW_RISK"
    OUTPUT_TRUNCATION    = "OUTPUT_TRUNCATION"
    TOOL_CALL_FAILURE    = "TOOL_CALL_FAILURE"
    TOOL_ARGUMENT_ERROR  = "TOOL_ARGUMENT_ERROR"
    RETRY_LOOP           = "RETRY_LOOP"
    MODEL_TIMEOUT        = "MODEL_TIMEOUT"
    MODEL_RATE_LIMIT     = "MODEL_RATE_LIMIT"
    LATENCY_SPIKE        = "LATENCY_SPIKE"
    COST_SPIKE           = "COST_SPIKE"
    HALLUCINATION_RISK   = "HALLUCINATION_RISK"
    VALIDATION_FAILURE   = "VALIDATION_FAILURE"
    PROMPT_REGRESSION    = "PROMPT_REGRESSION"
    UNKNOWN_FAILURE      = "UNKNOWN_FAILURE"


class FailureSeverity(str, enum.Enum):
    LOW      = "LOW"
    MEDIUM   = "MEDIUM"
    HIGH     = "HIGH"
    CRITICAL = "CRITICAL"


class IncidentStatus(str, enum.Enum):
    OPEN         = "OPEN"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED     = "RESOLVED"


class AlertMetric(str, enum.Enum):
    success_rate      = "success_rate"
    avg_latency_ms    = "avg_latency_ms"
    avg_cost          = "avg_cost"
    open_incidents    = "open_incidents"
    reliability_score = "reliability_score"


class AlertOperator(str, enum.Enum):
    lt  = "lt"
    lte = "lte"
    gt  = "gt"
    gte = "gte"


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
    original_run_id     = Column(UUID(as_uuid=False), ForeignKey("workflow_runs.id"), nullable=True)
    is_replay           = Column(Boolean, nullable=False, default=False)
    metadata_           = Column("metadata", JSONB, nullable=True)
    reliability_score   = Column(Integer, nullable=True)
    reliability_reasons = Column(JSONB, nullable=True)

    steps      = relationship("TraceStep", back_populates="run", cascade="all, delete-orphan")
    llm_calls  = relationship("LLMCall", back_populates="run", cascade="all, delete-orphan")
    evaluations = relationship("EvaluationResult", back_populates="run", cascade="all, delete-orphan")
    feedback   = relationship("HumanFeedback", back_populates="run", cascade="all, delete-orphan")
    classifications = relationship("FailureClassification", back_populates="run", cascade="all, delete-orphan")


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


class SpanEvent(Base):
    """
    Raw span events ingested from the SDK via POST /v1/ingest/batch.

    This table is the source of truth for the agent graph, diagnostics,
    and real-time streaming. It is append-only — spans are never updated.
    """
    __tablename__ = "span_events"

    id             = Column(Integer, primary_key=True, autoincrement=True)
    span_id        = Column(String(64),  nullable=False, index=True)
    trace_id       = Column(String(64),  nullable=False, index=True)
    parent_span_id = Column(String(64),  nullable=True,  index=True)
    run_id         = Column(String(64),  nullable=True,  index=True)
    name           = Column(String(255), nullable=False)
    kind           = Column(String(64),  nullable=False, default="step")
    event_type     = Column(String(64),  nullable=False)
    status         = Column(String(32),  nullable=False, default="unset")
    error_message  = Column(Text,        nullable=True)
    attributes     = Column(JSONB,       nullable=True,  default=dict)
    timestamp_ns   = Column(BigInteger,  nullable=False, default=0)
    duration_ns    = Column(BigInteger,  nullable=True)
    created_at     = Column(DateTime(timezone=True), nullable=False, default=_now)


# ─── Failure Classification ───────────────────────────────────────────────────

class FailureClassification(Base):
    __tablename__ = "failure_classifications"

    id             = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    run_id         = Column(UUID(as_uuid=False), ForeignKey("workflow_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    step_id        = Column(UUID(as_uuid=False), nullable=True)
    category       = Column(String(64), nullable=False, index=True)
    severity       = Column(String(16), nullable=False, default=FailureSeverity.MEDIUM.value)
    evidence       = Column(JSONB, nullable=True)
    recommendation = Column(Text, nullable=True)
    created_at     = Column(DateTime(timezone=True), nullable=False, default=_now)

    run = relationship("WorkflowRun", back_populates="classifications")


# ─── Incidents ────────────────────────────────────────────────────────────────

# Association table — many incidents ↔ many runs
incident_runs = Table(
    "incident_runs",
    Base.metadata,
    Column("incident_id", UUID(as_uuid=False), ForeignKey("incidents.id",       ondelete="CASCADE"), primary_key=True),
    Column("run_id",      UUID(as_uuid=False), ForeignKey("workflow_runs.id",    ondelete="CASCADE"), primary_key=True),
    Column("linked_at",   DateTime(timezone=True), nullable=False, default=_now),
)


class Incident(Base):
    __tablename__ = "incidents"

    id                 = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    title              = Column(String(255), nullable=False)
    category           = Column(String(64),  nullable=False, index=True)
    severity           = Column(String(16),  nullable=False, default=FailureSeverity.MEDIUM.value)
    status             = Column(String(16),  nullable=False, default=IncidentStatus.OPEN.value, index=True)
    workflow_name      = Column(String(255), nullable=True, index=True)
    occurrence_count   = Column(Integer,     nullable=False, default=1)
    first_seen_at      = Column(DateTime(timezone=True), nullable=False, default=_now)
    last_seen_at       = Column(DateTime(timezone=True), nullable=False, default=_now)
    evidence           = Column(JSONB, nullable=True)
    recommended_action = Column(Text,  nullable=True)
    resolved_at        = Column(DateTime(timezone=True), nullable=True)
    created_at         = Column(DateTime(timezone=True), nullable=False, default=_now)

    runs = relationship("WorkflowRun", secondary=incident_runs, backref="incidents")


# ─── Alert Rules ──────────────────────────────────────────────────────────────

class AlertRule(Base):
    __tablename__ = "alert_rules"

    id             = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    name           = Column(String(255), nullable=False)
    metric         = Column(String(32),  nullable=False)   # AlertMetric value
    operator       = Column(String(8),   nullable=False)   # AlertOperator value
    threshold      = Column(Float,       nullable=False)
    window_minutes = Column(Integer,     nullable=False, default=60)
    severity       = Column(String(16),  nullable=False, default=FailureSeverity.MEDIUM.value)
    workflow_name  = Column(String(255), nullable=True, index=True)
    enabled        = Column(Boolean,     nullable=False, default=True)
    created_at     = Column(DateTime(timezone=True), nullable=False, default=_now)

    firings = relationship("AlertFiring", back_populates="rule", cascade="all, delete-orphan")


class AlertFiring(Base):
    __tablename__ = "alert_firings"

    id           = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    rule_id      = Column(UUID(as_uuid=False), ForeignKey("alert_rules.id", ondelete="CASCADE"), nullable=False, index=True)
    metric_value = Column(Float,  nullable=False)
    fired_at     = Column(DateTime(timezone=True), nullable=False, default=_now)
    resolved_at  = Column(DateTime(timezone=True), nullable=True)
    is_active    = Column(Boolean, nullable=False, default=True)

    rule = relationship("AlertRule", back_populates="firings")
