"""Webhook delivery service.

Delivers signed HTTP POST payloads to configured destinations when alert
rules fire or resolve. Each attempt is recorded in WebhookDelivery for
auditability and debugging.

Signature: when a secret is configured, the request includes
  X-TraceChain-Signature: sha256=<hmac_hex>
computed over the raw JSON body using HMAC-SHA256.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone

import httpx
from sqlalchemy.orm import Session

from ..models import AlertFiring, AlertRule, WebhookDelivery, WebhookDestination

logger = logging.getLogger("tracechain.webhooks")

_TIMEOUT = 8.0   # seconds per delivery attempt


def _sign(body: bytes, secret: str) -> str:
    mac = hmac.new(secret.encode(), body, hashlib.sha256)
    return f"sha256={mac.hexdigest()}"


def _build_payload(event_type: str, firing: AlertFiring, rule: AlertRule) -> dict:
    return {
        "event":     event_type,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "rule": {
            "id":            rule.id,
            "name":          rule.name,
            "metric":        rule.metric,
            "operator":      rule.operator,
            "threshold":     rule.threshold,
            "severity":      rule.severity,
            "workflow_name": rule.workflow_name,
        },
        "firing": {
            "id":           firing.id,
            "metric_value": firing.metric_value,
            "fired_at":     firing.fired_at.isoformat()
                            if firing.fired_at else None,
            "resolved_at":  firing.resolved_at.isoformat()
                            if getattr(firing, "resolved_at", None) else None,
        },
    }


def _deliver_one(
    db: Session,
    dest: WebhookDestination,
    event_type: str,
    firing: AlertFiring,
    rule: AlertRule,
) -> None:
    payload_dict = _build_payload(event_type, firing, rule)
    body = json.dumps(payload_dict).encode()

    headers: dict[str, str] = {
        "Content-Type": "application/json",
        "X-TraceChain-Event": event_type,
    }
    if dest.secret:
        headers["X-TraceChain-Signature"] = _sign(body, dest.secret)

    status_code = None
    success      = False
    error_msg    = None

    try:
        with httpx.Client(timeout=_TIMEOUT) as client:
            resp = client.post(dest.url, content=body, headers=headers)
        status_code = resp.status_code
        success     = 200 <= resp.status_code < 300
        if not success:
            error_msg = f"HTTP {resp.status_code}: {resp.text[:200]}"
    except Exception as exc:
        error_msg = str(exc)[:500]
        logger.warning("webhook delivery to %s failed: %s", dest.url, error_msg)

    delivery = WebhookDelivery(
        destination_id = dest.id,
        event_type     = event_type,
        payload        = payload_dict,
        status_code    = status_code,
        success        = success,
        error_message  = error_msg,
        attempted_at   = datetime.now(timezone.utc),
    )
    db.add(delivery)
    db.flush()


def deliver_alert_events(
    db: Session,
    new_firings: list[AlertFiring],
    resolved_firings: list[AlertFiring],
) -> None:
    """Deliver webhook notifications for newly fired and resolved alerts."""
    if not new_firings and not resolved_firings:
        return

    destinations = (
        db.query(WebhookDestination)
          .filter(WebhookDestination.enabled == True)  # noqa: E712
          .all()
    )
    if not destinations:
        return

    for firing in new_firings:
        rule = db.query(AlertRule).filter(AlertRule.id == firing.rule_id).first()
        if not rule:
            continue
        for dest in destinations:
            try:
                _deliver_one(db, dest, "alert.fired", firing, rule)
            except Exception:
                logger.exception("unexpected error delivering to %s", dest.url)

    for firing in resolved_firings:
        rule = db.query(AlertRule).filter(AlertRule.id == firing.rule_id).first()
        if not rule:
            continue
        for dest in destinations:
            try:
                _deliver_one(db, dest, "alert.resolved", firing, rule)
            except Exception:
                logger.exception("unexpected error delivering to %s", dest.url)

    try:
        db.commit()
    except Exception:
        logger.exception("failed to commit webhook delivery records")
