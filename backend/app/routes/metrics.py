from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas import (
    OverviewMetrics, LatencyPoint, CostPoint, FailurePoint, TimeSeriesPoint,
    ClassificationBreakdownPoint, IncidentSummary, WorkflowHealth,
)
from ..services import metrics as metrics_svc

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("/overview", response_model=OverviewMetrics)
def overview(db: Session = Depends(get_db)):
    return metrics_svc.get_overview(db)


@router.get("/latency", response_model=list[LatencyPoint])
def latency(days: int = Query(30, ge=1, le=90), db: Session = Depends(get_db)):
    return metrics_svc.get_latency(db, days)


@router.get("/cost", response_model=list[CostPoint])
def cost(days: int = Query(30, ge=1, le=90), db: Session = Depends(get_db)):
    return metrics_svc.get_cost(db, days)


@router.get("/failures", response_model=list[FailurePoint])
def failures(days: int = Query(30, ge=1, le=90), db: Session = Depends(get_db)):
    return metrics_svc.get_failures(db, days)


@router.get("/prompts", response_model=list[LatencyPoint])
def prompts_metrics(db: Session = Depends(get_db)):
    return metrics_svc.get_latency(db)  # per-workflow breakdown, sufficient for v1


@router.get("/timeseries/success-rate", response_model=list[TimeSeriesPoint])
def success_rate_timeseries(days: int = Query(14, ge=1, le=90), db: Session = Depends(get_db)):
    return metrics_svc.get_success_rate_timeseries(db, days)


@router.get("/timeseries/cost", response_model=list[TimeSeriesPoint])
def cost_timeseries(days: int = Query(14, ge=1, le=90), db: Session = Depends(get_db)):
    return metrics_svc.get_cost_timeseries(db, days)


@router.get("/timeseries/latency", response_model=list[TimeSeriesPoint])
def latency_timeseries(days: int = Query(14, ge=1, le=90), db: Session = Depends(get_db)):
    return metrics_svc.get_latency_timeseries(db, days)


@router.get("/timeseries/runs", response_model=list[TimeSeriesPoint])
def runs_timeseries(days: int = Query(14, ge=1, le=90), db: Session = Depends(get_db)):
    return metrics_svc.get_runs_timeseries(db, days)


@router.get("/timeseries/quality", response_model=list[TimeSeriesPoint])
def quality_timeseries(days: int = Query(14, ge=1, le=90), db: Session = Depends(get_db)):
    return metrics_svc.get_quality_timeseries(db, days)


@router.get("/timeseries/tokens", response_model=list[TimeSeriesPoint])
def tokens_timeseries(days: int = Query(14, ge=1, le=90), db: Session = Depends(get_db)):
    return metrics_svc.get_tokens_timeseries(db, days)


@router.get("/timeseries/reliability", response_model=list[TimeSeriesPoint])
def reliability_timeseries(
    days: int = Query(14, ge=1, le=90),
    workflow_name: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    return metrics_svc.get_reliability_timeseries(db, days, workflow_name)


@router.get("/failures/classification", response_model=list[ClassificationBreakdownPoint])
def classification_breakdown(
    days: int = Query(14, ge=1, le=90),
    workflow_name: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    return metrics_svc.get_classification_breakdown(db, days, workflow_name)


@router.get("/incidents/summary", response_model=IncidentSummary)
def incident_summary(db: Session = Depends(get_db)):
    return metrics_svc.get_incident_summary(db)


@router.get("/workflows", response_model=list[WorkflowHealth])
def workflow_health(
    days: int = Query(30, ge=1, le=90),
    db: Session = Depends(get_db),
):
    return metrics_svc.get_workflow_health(db, days)
