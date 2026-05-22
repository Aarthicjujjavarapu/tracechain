from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import CostBudget
from ..schemas import BudgetCreate, BudgetUpdate, BudgetOut, BudgetStatusOut, SpendSummary
from ..services import budget as budget_svc

router = APIRouter(prefix="/budgets", tags=["budgets"])


@router.get("/spend-summary", response_model=SpendSummary)
def spend_summary(db: Session = Depends(get_db)):
    return budget_svc.get_spend_summary(db)


@router.get("", response_model=list[BudgetStatusOut])
def list_budgets(db: Session = Depends(get_db)):
    return [budget_svc.get_budget_status(db, b) for b in budget_svc.list_budgets(db)]


@router.post("", response_model=BudgetOut, status_code=201)
def create_budget(data: BudgetCreate, db: Session = Depends(get_db)):
    return budget_svc.create_budget(db, data)


@router.get("/{budget_id}", response_model=BudgetStatusOut)
def get_budget(budget_id: str, db: Session = Depends(get_db)):
    b = db.query(CostBudget).filter(CostBudget.id == budget_id).first()
    if not b:
        raise HTTPException(status_code=404, detail=f"Budget {budget_id} not found")
    return budget_svc.get_budget_status(db, b)


@router.patch("/{budget_id}", response_model=BudgetOut)
def update_budget(budget_id: str, data: BudgetUpdate, db: Session = Depends(get_db)):
    b = budget_svc.update_budget(db, budget_id, data)
    if not b:
        raise HTTPException(status_code=404, detail=f"Budget {budget_id} not found")
    return b


@router.delete("/{budget_id}", status_code=204)
def delete_budget(budget_id: str, db: Session = Depends(get_db)):
    if not budget_svc.delete_budget(db, budget_id):
        raise HTTPException(status_code=404, detail=f"Budget {budget_id} not found")
