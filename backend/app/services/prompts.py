from sqlalchemy.orm import Session
from fastapi import HTTPException

from ..models import PromptVersion, LLMCall, EvaluationResult, LLMStatus
from ..schemas import PromptCreate, PromptMetrics, CompareWinner, PromptCompareOut


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


def _metrics_for(db: Session, pv: PromptVersion) -> PromptMetrics:
    calls = (
        db.query(LLMCall)
        .filter(LLMCall.prompt_version == pv.version)
        .all()
    )
    usage_count = len(calls)
    if usage_count == 0:
        return PromptMetrics(
            prompt_id=pv.id, prompt_name=pv.prompt_name, version=pv.version,
            usage_count=0, avg_latency_ms=None, avg_cost=None,
            success_rate=0.0, avg_quality_score=None,
        )
    latencies     = [c.latency_ms      for c in calls if c.latency_ms      is not None]
    costs         = [c.estimated_cost  for c in calls if c.estimated_cost  is not None]
    successes     = sum(1 for c in calls if c.status == LLMStatus.success)
    run_ids       = list({c.run_id for c in calls})
    evals         = db.query(EvaluationResult).filter(EvaluationResult.run_id.in_(run_ids)).all()
    quality_scores = [e.quality_score for e in evals]
    return PromptMetrics(
        prompt_id=pv.id, prompt_name=pv.prompt_name, version=pv.version,
        usage_count=usage_count,
        avg_latency_ms=round(sum(latencies) / len(latencies), 1) if latencies else None,
        avg_cost=round(sum(costs) / len(costs), 6) if costs else None,
        success_rate=round(successes / usage_count, 4),
        avg_quality_score=round(sum(quality_scores) / len(quality_scores), 3) if quality_scores else None,
    )


def get_prompt_metrics(db: Session, prompt_id: str) -> PromptMetrics:
    return _metrics_for(db, get_prompt(db, prompt_id))


def _win(a: float | None, b: float | None, lower_is_better: bool = False) -> str | None:
    if a is None or b is None or a == b:
        return None
    return "a" if (a < b) == lower_is_better else "b"


def compare_prompts(db: Session, id_a: str, id_b: str) -> PromptCompareOut:
    pv_a = get_prompt(db, id_a)
    pv_b = get_prompt(db, id_b)
    if pv_a.prompt_name != pv_b.prompt_name:
        raise HTTPException(
            status_code=422,
            detail=f"Cannot compare prompts from different names: '{pv_a.prompt_name}' vs '{pv_b.prompt_name}'",
        )
    m_a = _metrics_for(db, pv_a)
    m_b = _metrics_for(db, pv_b)
    return PromptCompareOut(
        a=m_a,
        b=m_b,
        winner=CompareWinner(
            latency=_win(m_a.avg_latency_ms, m_b.avg_latency_ms, lower_is_better=True),
            cost=_win(m_a.avg_cost, m_b.avg_cost, lower_is_better=True),
            success_rate=_win(m_a.success_rate, m_b.success_rate),
            quality=_win(m_a.avg_quality_score, m_b.avg_quality_score),
        ),
    )
