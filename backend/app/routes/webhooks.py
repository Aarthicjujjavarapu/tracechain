from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import WebhookDelivery, WebhookDestination
from ..schemas import WebhookCreate, WebhookDeliveryOut, WebhookOut, WebhookUpdate

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.get("", response_model=list[WebhookOut])
def list_webhooks(db: Session = Depends(get_db)):
    return db.query(WebhookDestination).order_by(WebhookDestination.created_at.desc()).all()


@router.post("", response_model=WebhookOut, status_code=201)
def create_webhook(data: WebhookCreate, db: Session = Depends(get_db)):
    dest = WebhookDestination(**data.model_dump())
    db.add(dest)
    db.commit()
    db.refresh(dest)
    return dest


@router.get("/{dest_id}", response_model=WebhookOut)
def get_webhook(dest_id: str, db: Session = Depends(get_db)):
    dest = db.query(WebhookDestination).filter(WebhookDestination.id == dest_id).first()
    if not dest:
        raise HTTPException(status_code=404, detail="Webhook destination not found")
    return dest


@router.patch("/{dest_id}", response_model=WebhookOut)
def update_webhook(dest_id: str, data: WebhookUpdate, db: Session = Depends(get_db)):
    dest = db.query(WebhookDestination).filter(WebhookDestination.id == dest_id).first()
    if not dest:
        raise HTTPException(status_code=404, detail="Webhook destination not found")
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(dest, field, value)
    db.commit()
    db.refresh(dest)
    return dest


@router.delete("/{dest_id}", status_code=204)
def delete_webhook(dest_id: str, db: Session = Depends(get_db)):
    dest = db.query(WebhookDestination).filter(WebhookDestination.id == dest_id).first()
    if not dest:
        raise HTTPException(status_code=404, detail="Webhook destination not found")
    db.delete(dest)
    db.commit()


@router.get("/deliveries/recent", response_model=list[WebhookDeliveryOut])
def list_deliveries(
    limit:  int = Query(50, ge=1, le=200),
    failed: bool = Query(False),
    db: Session = Depends(get_db),
):
    q = db.query(WebhookDelivery)
    if failed:
        q = q.filter(WebhookDelivery.success == False)  # noqa: E712
    return q.order_by(WebhookDelivery.attempted_at.desc()).limit(limit).all()
