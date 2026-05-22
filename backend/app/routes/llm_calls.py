from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas import LLMCallCreate, LLMCallOut
from ..services import llm_calls as llm_svc

router = APIRouter(prefix="/runs", tags=["llm-calls"])


@router.post("/{run_id}/llm-calls", response_model=LLMCallOut, status_code=201)
def create_llm_call(run_id: str, data: LLMCallCreate, db: Session = Depends(get_db)):
    return llm_svc.create_llm_call(db, run_id, data)


@router.get("/{run_id}/llm-calls", response_model=list[LLMCallOut])
def list_llm_calls(run_id: str, db: Session = Depends(get_db)):
    return llm_svc.list_llm_calls(db, run_id)
