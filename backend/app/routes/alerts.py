from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import AlertFiring, AlertRule
from ..schemas import (
    AlertFiringOut, AlertRuleCreate, AlertRuleOut, AlertRuleUpdate, AlertSummary,
)

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("/rules", response_model=list[AlertRuleOut])
def list_rules(db: Session = Depends(get_db)):
    return db.query(AlertRule).order_by(AlertRule.created_at.desc()).all()


@router.post("/rules", response_model=AlertRuleOut, status_code=201)
def create_rule(data: AlertRuleCreate, db: Session = Depends(get_db)):
    rule = AlertRule(**data.model_dump())
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


@router.get("/rules/{rule_id}", response_model=AlertRuleOut)
def get_rule(rule_id: str, db: Session = Depends(get_db)):
    rule = db.query(AlertRule).filter(AlertRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Alert rule not found")
    return rule


@router.patch("/rules/{rule_id}", response_model=AlertRuleOut)
def update_rule(rule_id: str, data: AlertRuleUpdate, db: Session = Depends(get_db)):
    rule = db.query(AlertRule).filter(AlertRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Alert rule not found")
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(rule, field, value)
    db.commit()
    db.refresh(rule)
    return rule


@router.delete("/rules/{rule_id}", status_code=204)
def delete_rule(rule_id: str, db: Session = Depends(get_db)):
    rule = db.query(AlertRule).filter(AlertRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Alert rule not found")
    db.delete(rule)
    db.commit()


@router.get("/firings", response_model=list[AlertFiringOut])
def list_firings(
    active_only: bool = Query(False),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    q = db.query(AlertFiring)
    if active_only:
        q = q.filter(AlertFiring.is_active == True)  # noqa: E712
    return q.order_by(AlertFiring.fired_at.desc()).limit(limit).all()


@router.get("/summary", response_model=AlertSummary)
def alert_summary(db: Session = Depends(get_db)):
    return AlertSummary(
        total_rules   = db.query(AlertRule).count(),
        enabled_rules = db.query(AlertRule).filter(AlertRule.enabled == True).count(),  # noqa: E712
        firing_now    = db.query(AlertFiring).filter(AlertFiring.is_active == True).count(),  # noqa: E712
    )
