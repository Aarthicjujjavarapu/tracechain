from __future__ import annotations
from datetime import datetime
from typing import Any, Literal, Optional
from pydantic import BaseModel, Field
from .models import RunStatus, StepType, LLMStatus


# ─── WorkflowRun ──────────────────────────────────────────────────────────────

class RunCreate(BaseModel):
    workflow_name: str
    input_payload: dict[str, Any] = Field(default_factory=dict)
    metadata: Optional[dict[str, Any]] = None


class RunComplete(BaseModel):
    output_payload: Optional[Any] = None
    total_cost: Optional[float] = None
    total_tokens: Optional[int] = None


class RunFail(BaseModel):
    error_message: str


class RunOut(BaseModel):
    id: str
    workflow_name: str
    status: RunStatus
    input_payload: dict[str, Any]
    output_payload: Optional[Any]
    error_message: Optional[str]
    started_at: datetime
    ended_at: Optional[datetime]
    duration_ms: Optional[int]
    total_cost: Optional[float]
    total_tokens: Optional[int]
    original_run_id: Optional[str]
    is_replay: bool
    metadata: Optional[dict[str, Any]]
    reliability_score: Optional[int] = None
    reliability_reasons: Optional[list[str]] = None

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_model(cls, obj) -> "RunOut":
        return cls(
            id=obj.id,
            workflow_name=obj.workflow_name,
            status=obj.status,
            input_payload=obj.input_payload or {},
            output_payload=obj.output_payload,
            error_message=obj.error_message,
            started_at=obj.started_at,
            ended_at=obj.ended_at,
            duration_ms=obj.duration_ms,
            total_cost=obj.total_cost,
            total_tokens=obj.total_tokens,
            original_run_id=obj.original_run_id,
            is_replay=obj.is_replay,
            metadata=obj.metadata_,
            reliability_score=obj.reliability_score,
            reliability_reasons=obj.reliability_reasons,
        )


class RunListOut(BaseModel):
    items: list[RunOut]
    total: int


# ─── TraceStep ────────────────────────────────────────────────────────────────

class StepCreate(BaseModel):
    step_name: str
    step_type: StepType = StepType.step
    input_payload: dict[str, Any] = Field(default_factory=dict)
    metadata: Optional[dict[str, Any]] = None


class StepComplete(BaseModel):
    output_payload: Optional[Any] = None
    duration_ms: Optional[int] = None
    retry_count: int = 0


class StepFail(BaseModel):
    error_message: str
    retry_count: int = 0


class StepOut(BaseModel):
    id: str
    run_id: str
    step_name: str
    step_type: StepType
    status: RunStatus
    input_payload: dict[str, Any]
    output_payload: Optional[Any]
    error_message: Optional[str]
    started_at: datetime
    ended_at: Optional[datetime]
    duration_ms: Optional[int]
    retry_count: int
    metadata: Optional[dict[str, Any]]

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_model(cls, obj) -> "StepOut":
        return cls(
            id=obj.id,
            run_id=obj.run_id,
            step_name=obj.step_name,
            step_type=obj.step_type,
            status=obj.status,
            input_payload=obj.input_payload or {},
            output_payload=obj.output_payload,
            error_message=obj.error_message,
            started_at=obj.started_at,
            ended_at=obj.ended_at,
            duration_ms=obj.duration_ms,
            retry_count=obj.retry_count,
            metadata=obj.metadata_,
        )


# ─── LLMCall ──────────────────────────────────────────────────────────────────

class LLMCallCreate(BaseModel):
    step_id: Optional[str] = None
    provider: str = "openai"
    model: str
    prompt: str
    response: Optional[str] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    estimated_cost: Optional[float] = None
    latency_ms: Optional[int] = None
    time_to_first_token_ms: Optional[int] = None
    is_stream: bool = False
    temperature: Optional[float] = None
    status: LLMStatus = LLMStatus.success
    error_message: Optional[str] = None
    prompt_version: Optional[str] = None


class LLMCallOut(BaseModel):
    id: str
    run_id: str
    step_id: Optional[str]
    provider: str
    model: str
    prompt: str
    response: Optional[str]
    input_tokens: Optional[int]
    output_tokens: Optional[int]
    total_tokens: Optional[int]
    estimated_cost: Optional[float]
    latency_ms: Optional[int]
    time_to_first_token_ms: Optional[int]
    is_stream: bool
    temperature: Optional[float]
    status: LLMStatus
    error_message: Optional[str]
    prompt_version: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


# ─── PromptVersion ────────────────────────────────────────────────────────────

class PromptCreate(BaseModel):
    prompt_name: str
    version: str
    prompt_text: str
    is_active: bool = True
    metadata: Optional[dict[str, Any]] = None


class PromptOut(BaseModel):
    id: str
    prompt_name: str
    version: str
    prompt_text: str
    is_active: bool
    metadata: Optional[dict[str, Any]]
    created_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_model(cls, obj) -> "PromptOut":
        return cls(
            id=obj.id,
            prompt_name=obj.prompt_name,
            version=obj.version,
            prompt_text=obj.prompt_text,
            is_active=obj.is_active,
            metadata=obj.metadata_,
            created_at=obj.created_at,
        )


class PromptMetrics(BaseModel):
    prompt_id: str
    prompt_name: str
    version: str
    usage_count: int
    avg_latency_ms: Optional[float]
    avg_cost: Optional[float]
    success_rate: float
    avg_quality_score: Optional[float]


# ─── EvaluationResult ─────────────────────────────────────────────────────────

class EvalCreate(BaseModel):
    relevance_score: float = Field(ge=0.0, le=1.0)
    groundedness_score: float = Field(ge=0.0, le=1.0)
    hallucination_risk: float = Field(ge=0.0, le=1.0)
    quality_score: float = Field(ge=0.0, le=1.0)
    failure_reason: Optional[str] = None


class EvalOut(BaseModel):
    id: str
    run_id: str
    relevance_score: float
    groundedness_score: float
    hallucination_risk: float
    quality_score: float
    failure_reason: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


# ─── HumanFeedback ────────────────────────────────────────────────────────────

class FeedbackCreate(BaseModel):
    rating: int = Field(ge=1, le=5)
    comment: Optional[str] = None


class FeedbackOut(BaseModel):
    id: str
    run_id: str
    rating: int
    comment: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


# ─── Metrics ──────────────────────────────────────────────────────────────────

class OverviewMetrics(BaseModel):
    total_runs: int
    success_rate: float
    avg_latency_ms: float
    total_cost: float
    total_tokens: int
    failure_count: int


class LatencyPoint(BaseModel):
    workflow_name: str
    avg_latency_ms: float
    p95_latency_ms: float
    run_count: int


class CostPoint(BaseModel):
    model: str
    total_cost: float
    call_count: int


class FailurePoint(BaseModel):
    step_name: str
    failure_count: int
    total_count: int
    failure_rate: float


class TimeSeriesPoint(BaseModel):
    date: str
    value: float


class HealthOut(BaseModel):
    status: str
    version: str = "0.1.0"


# ─── FailureClassification ────────────────────────────────────────────────────

class FailureClassificationOut(BaseModel):
    id:             str
    run_id:         str
    step_id:        Optional[str]
    category:       str
    severity:       str
    evidence:       Optional[dict[str, Any]]
    recommendation: Optional[str]
    created_at:     datetime

    model_config = {"from_attributes": True}


# ─── Reliability ──────────────────────────────────────────────────────────────

class ReliabilityOut(BaseModel):
    run_id:  str
    score:   int
    reasons: list[str]


# ─── Incidents ────────────────────────────────────────────────────────────────

class IncidentOut(BaseModel):
    id:                 str
    title:              str
    category:           str
    severity:           str
    status:             str
    workflow_name:      Optional[str]
    occurrence_count:   int
    first_seen_at:      datetime
    last_seen_at:       datetime
    evidence:           Optional[dict[str, Any]]
    recommended_action: Optional[str]
    resolved_at:        Optional[datetime]
    created_at:         datetime

    model_config = {"from_attributes": True}


class IncidentListOut(BaseModel):
    items: list[IncidentOut]
    total: int


class IncidentUpdate(BaseModel):
    status: str  # ACKNOWLEDGED | RESOLVED


# ─── Reliability Analytics ────────────────────────────────────────────────────

class ClassificationBreakdownPoint(BaseModel):
    category: str
    count: int
    pct: float


class IncidentSummary(BaseModel):
    open: int
    acknowledged: int
    resolved: int
    total: int


class WorkflowHealth(BaseModel):
    workflow_name:        str
    run_count:            int
    avg_reliability_score: Optional[float]
    success_rate:         float
    open_incidents:       int
    top_failure_category: Optional[str]
    trend:                str   # "improving" | "degrading" | "stable" | "insufficient_data"
    trend_delta:          Optional[float]


# ─── Alert Rules ──────────────────────────────────────────────────────────────

class AlertRuleCreate(BaseModel):
    name:           str
    metric:         Literal["success_rate", "avg_latency_ms", "avg_cost", "open_incidents", "reliability_score"]
    operator:       Literal["lt", "lte", "gt", "gte"]
    threshold:      float
    window_minutes: int = Field(default=60, ge=1)
    severity:       str = "MEDIUM"
    workflow_name:  Optional[str] = None
    enabled:        bool = True


class AlertRuleUpdate(BaseModel):
    name:           Optional[str]   = None
    threshold:      Optional[float] = None
    window_minutes: Optional[int]   = None
    severity:       Optional[str]   = None
    enabled:        Optional[bool]  = None
    workflow_name:  Optional[str]   = None


class AlertRuleOut(BaseModel):
    id:             str
    name:           str
    metric:         str
    operator:       str
    threshold:      float
    window_minutes: int
    severity:       str
    workflow_name:  Optional[str]
    enabled:        bool
    created_at:     datetime

    model_config = {"from_attributes": True}


class AlertFiringOut(BaseModel):
    id:           str
    rule_id:      str
    metric_value: float
    fired_at:     datetime
    resolved_at:  Optional[datetime]
    is_active:    bool

    model_config = {"from_attributes": True}


class AlertSummary(BaseModel):
    total_rules:   int
    enabled_rules: int
    firing_now:    int


# ─── Webhooks ─────────────────────────────────────────────────────────────────

class WebhookCreate(BaseModel):
    name:    str
    url:     str
    secret:  Optional[str] = None
    enabled: bool = True


class WebhookUpdate(BaseModel):
    name:    Optional[str]  = None
    url:     Optional[str]  = None
    secret:  Optional[str]  = None
    enabled: Optional[bool] = None


class WebhookOut(BaseModel):
    id:         str
    name:       str
    url:        str
    secret:     Optional[str]
    enabled:    bool
    created_at: datetime

    model_config = {"from_attributes": True}


class WebhookDeliveryOut(BaseModel):
    id:             str
    destination_id: str
    event_type:     str
    payload:        dict
    status_code:    Optional[int]
    success:        bool
    attempted_at:   datetime
    error_message:  Optional[str]

    model_config = {"from_attributes": True}


# ─── Cost Budgets ─────────────────────────────────────────────────────────────

class BudgetCreate(BaseModel):
    name:          str
    workflow_name: Optional[str]  = None
    budget_usd:    float          = Field(gt=0)
    period:        Literal["daily", "monthly", "total"] = "monthly"
    warning_pct:   float          = Field(default=0.75, gt=0, lt=1)
    enabled:       bool           = True


class BudgetUpdate(BaseModel):
    name:        Optional[str]   = None
    budget_usd:  Optional[float] = Field(default=None, gt=0)
    period:      Optional[str]   = None
    warning_pct: Optional[float] = None
    enabled:     Optional[bool]  = None


class BudgetOut(BaseModel):
    id:            str
    name:          str
    workflow_name: Optional[str]
    budget_usd:    float
    period:        str
    warning_pct:   float
    enabled:       bool
    created_at:    datetime

    model_config = {"from_attributes": True}


class BudgetStatusOut(BudgetOut):
    spent:                 float
    remaining:             float
    pct_used:              float
    status:                str            # ok | warning | critical | exceeded
    projected_monthly_usd: Optional[float]
    window_start:          Optional[str]


class SpendSummary(BaseModel):
    today_usd:       float
    month_usd:       float
    all_time_usd:    float
    run_count_today: int
    run_count_month: int
