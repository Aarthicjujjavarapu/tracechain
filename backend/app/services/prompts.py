from sqlalchemy.orm import Session
from fastapi import HTTPException

from ..models import PromptVersion, LLMCall, EvaluationResult, LLMStatus
from ..schemas import PromptCreate, PromptMetrics


def create_prompt(db: Session, data: PromptCreate) -> PromptVersion:
    pv = PromptVersion(
        prompt_name=data.prompt_name,
        version=data.version,
        prompt_text=data.prompt_text,
        is_active=data.is_active,
        metadata_=data.metadata,
    )
    db.add(pv)
    db.commit()
    db.refresh(pv)
    return pv


def list_prompts(db: Session) -> list[PromptVersion]:
    return db.query(PromptVersion).order_by(PromptVersion.prompt_name, PromptVersion.version).all()


def get_prompt(db: Session, prompt_id: str) -> PromptVersion:
    pv = db.query(PromptVersion).filter(PromptVersion.id == prompt_id).first()
    if not pv:
        raise HTTPException(status_code=404, detail=f"Prompt {prompt_id} not found")
    return pv


def get_prompt_metrics(db: Session, prompt_id: str) -> PromptMetrics:
    pv = get_prompt(db, prompt_id)

    calls = (
        db.query(LLMCall)
        .filter(LLMCall.prompt_version == pv.version)
        .all()
    )

    usage_count = len(calls)
    if usage_count == 0:
        return PromptMetrics(
            prompt_id=pv.id,
            prompt_name=pv.prompt_name,
            version=pv.version,
            usage_count=0,
            avg_latency_ms=None,
            avg_cost=None,
            success_rate=0.0,
            avg_quality_score=None,
        )

    latencies = [c.latency_ms for c in calls if c.latency_ms is not None]
    costs = [c.estimated_cost for c in calls if c.estimated_cost is not None]
    successes = sum(1 for c in calls if c.status == LLMStatus.success)

    # pull eval scores for runs that used this prompt version
    run_ids = list({c.run_id for c in calls})
    evals = (
        db.query(EvaluationResult)
        .filter(EvaluationResult.run_id.in_(run_ids))
        .all()
    )
    quality_scores = [e.quality_score for e in evals]

    return PromptMetrics(
        prompt_id=pv.id,
        prompt_name=pv.prompt_name,
        version=pv.version,
        usage_count=usage_count,
        avg_latency_ms=round(sum(latencies) / len(latencies), 1) if latencies else None,
        avg_cost=round(sum(costs) / len(costs), 6) if costs else None,
        success_rate=round(successes / usage_count, 4),
        avg_quality_score=round(sum(quality_scores) / len(quality_scores), 3) if quality_scores else None,
    )
