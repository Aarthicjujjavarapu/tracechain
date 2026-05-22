from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas import IncidentOut, IncidentListOut, IncidentUpdate
from ..services.incidents import get_incidents, acknowledge_incident, resolve_incident

router = APIRouter(prefix="/incidents", tags=["incidents"])


@router.get("", response_model=IncidentListOut)
def list_incidents(
    status:        Optional[str] = Query(None),
    severity:      Optional[str] = Query(None),
    workflow_name: Optional[str] = Query(None),
    category:      Optional[str] = Query(None),
    offset: int = Query(0, ge=0),
    limit:  int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    items, total = get_incidents(db, status, severity, workflow_name, category, offset, limit)
    return IncidentListOut(items=[IncidentOut.model_validate(i) for i in items], total=total)


@router.patch("/{incident_id}", response_model=IncidentOut)
def update_incident(incident_id: str, data: IncidentUpdate, db: Session = Depends(get_db)):
    if data.status == "ACKNOWLEDGED":
        inc = acknowledge_incident(db, incident_id)
    elif data.status == "RESOLVED":
        inc = resolve_incident(db, incident_id)
    else:
        raise HTTPException(status_code=422, detail="status must be ACKNOWLEDGED or RESOLVED")
    if not inc:
        raise HTTPException(status_code=404, detail=f"Incident {incident_id} not found")
    return IncidentOut.model_validate(inc)
