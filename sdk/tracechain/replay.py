"""
Replay helpers — re-run a previous workflow run from the backend.
"""
import logging
from typing import Optional

from .client import get_default_client

logger = logging.getLogger("tracechain.replay")


def create_replay_metadata(original_run_id: str) -> dict:
    """Returns metadata dict that can be passed to @workflow's metadata param."""
    return {"original_run_id": original_run_id, "is_replay": True}


def trigger_replay(run_id: str, client=None) -> Optional[str]:
    """
    POST /runs/{run_id}/replay → creates a new run linked to the original.
    Returns the new run_id or None if the request failed.
    """
    tc = client or get_default_client()
    new_id = tc.trigger_replay(run_id)
    if new_id:
        logger.info(f"[TraceChain] Replay triggered. New run ID: {new_id}")
    return new_id
