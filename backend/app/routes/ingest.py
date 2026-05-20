"""
High-throughput batch ingestion endpoint.

POST /v1/ingest/batch  { "events": [...] }

Design constraints:
- Must return 200 in < 50ms regardless of downstream processing time.
- Events are processed asynchronously after the response is sent.
- Malformed events are silently dropped (never 422 the SDK).
- The WebSocket manager is notified for real-time dashboard updates.
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from ..database import get_db
from ..ws.manager import manager as ws_manager

logger = logging.getLogger("tracechain.ingest")

router = APIRouter(prefix="/v1/ingest", tags=["ingest"])


class IngestBatch(BaseModel):
    events: list[dict[str, Any]]

    @field_validator("events")
    @classmethod
    def limit_batch_size(cls, v: list) -> list:
        if len(v) > 5000:
            raise ValueError("Batch size exceeds maximum of 5000 events")
        return v


class IngestResponse(BaseModel):
    received: int
    dropped:  int


@router.post("/batch", response_model=IngestResponse)
async def ingest_batch(
    payload:     IngestBatch,
    background:  BackgroundTasks,
    db:          Session = Depends(get_db),
) -> IngestResponse:
    valid, dropped = _validate(payload.events)
    background.add_task(_process_events, valid, db)
    return IngestResponse(received=len(valid), dropped=dropped)


# ── processing ────────────────────────────────────────────────────────────────

def _validate(events: list[dict]) -> tuple[list[dict], int]:
    valid:   list[dict] = []
    dropped: int        = 0
    for evt in events:
        if not isinstance(evt, dict):
            dropped += 1
            continue
        if not evt.get("event_type") or not evt.get("span_id"):
            dropped += 1
            continue
        valid.append(evt)
    return valid, dropped


async def _process_events(events: list[dict], db: Session) -> None:
    """
    Background task: persist events to DB and broadcast to WebSocket clients.

    Currently writes to the spans table (created below) and broadcasts each
    event to connected WS clients. In a high-scale deployment this would
    publish to a queue (Redis Streams / Kafka) instead.
    """
    from ..models import SpanEvent
    from sqlalchemy.exc import SQLAlchemyError

    for evt in events:
        try:
            span = SpanEvent(
                span_id=evt.get("span_id", ""),
                trace_id=evt.get("trace_id", ""),
                parent_span_id=evt.get("parent_span_id"),
                run_id=evt.get("run_id"),
                name=evt.get("name", ""),
                kind=evt.get("kind", "step"),
                event_type=evt.get("event_type", ""),
                status=evt.get("status", "unset"),
                error_message=evt.get("error_message"),
                attributes=evt.get("attributes", {}),
                timestamp_ns=evt.get("timestamp_ns", 0),
                duration_ns=evt.get("duration_ns"),
            )
            db.add(span)
        except Exception as exc:
            logger.debug("Failed to persist event %s: %s", evt.get("span_id"), exc)

    try:
        db.commit()
    except SQLAlchemyError as exc:
        logger.warning("Batch commit failed: %s", exc)
        db.rollback()

    # broadcast to WebSocket clients (fire-and-forget)
    for evt in events:
        try:
            await ws_manager.broadcast(evt)
        except Exception:
            pass
