from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas import PromptCreate, PromptOut, PromptMetrics, PromptCompareOut
from ..services import prompts as prompt_svc

router = APIRouter(prefix="/prompts", tags=["prompts"])


@router.post("", response_model=PromptOut, status_code=201)
def create_prompt(data: PromptCreate, db: Session = Depends(get_db)):
    return PromptOut.from_orm_model(prompt_svc.create_prompt(db, data))


@router.get("", response_model=list[PromptOut])
def list_prompts(db: Session = Depends(get_db)):
    return [PromptOut.from_orm_model(p) for p in prompt_svc.list_prompts(db)]


@router.get("/compare", response_model=PromptCompareOut)
def compare_prompts(
    a: str = Query(..., description="Prompt ID for version A"),
    b: str = Query(..., description="Prompt ID for version B"),
    db: Session = Depends(get_db),
):
    return prompt_svc.compare_prompts(db, a, b)


@router.get("/{prompt_id}", response_model=PromptOut)
def get_prompt(prompt_id: str, db: Session = Depends(get_db)):
    return PromptOut.from_orm_model(prompt_svc.get_prompt(db, prompt_id))


@router.get("/{prompt_id}/metrics", response_model=PromptMetrics)
def get_prompt_metrics(prompt_id: str, db: Session = Depends(get_db)):
    return prompt_svc.get_prompt_metrics(db, prompt_id)
