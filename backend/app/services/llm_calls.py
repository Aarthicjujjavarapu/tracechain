from sqlalchemy.orm import Session

from ..models import LLMCall
from ..schemas import LLMCallCreate


def create_llm_call(db: Session, run_id: str, data: LLMCallCreate) -> LLMCall:
    call = LLMCall(
        run_id=run_id,
        step_id=data.step_id,
        provider=data.provider,
        model=data.model,
        prompt=data.prompt,
        response=data.response,
        input_tokens=data.input_tokens,
        output_tokens=data.output_tokens,
        total_tokens=data.total_tokens,
        estimated_cost=data.estimated_cost,
        latency_ms=data.latency_ms,
        time_to_first_token_ms=data.time_to_first_token_ms,
        is_stream=data.is_stream,
        temperature=data.temperature,
        status=data.status,
        error_message=data.error_message,
        prompt_version=data.prompt_version,
    )
    db.add(call)
    db.commit()
    db.refresh(call)
    return call


def list_llm_calls(db: Session, run_id: str) -> list[LLMCall]:
    return (
        db.query(LLMCall)
        .filter(LLMCall.run_id == run_id)
        .order_by(LLMCall.created_at)
        .all()
    )
