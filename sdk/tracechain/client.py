"""
HTTP client that sends traces to the TraceChain backend.

Design contract: every public method is *silent on failure*. If the backend is
unreachable or returns an error, the method logs a warning and returns None.
The user's workflow must never crash because of the SDK.
"""
import logging
from typing import Any, Optional

import httpx

from .config import TraceChainConfig

logger = logging.getLogger("tracechain.client")


class TraceChainClient:
    def __init__(self, config: Optional[TraceChainConfig] = None):
        self.config = config or TraceChainConfig.default()

    # ── internal ──────────────────────────────────────────────────────────────

    def _post(self, path: str, body: dict) -> Optional[dict]:
        if not self.config.enabled:
            return None
        url = f"{self.config.base_url}{path}"
        try:
            resp = httpx.post(url, json=body, timeout=self.config.timeout)
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            logger.warning(f"[TraceChain] POST {path} failed: {exc}")
            return None

    def _patch(self, path: str, body: dict) -> Optional[dict]:
        if not self.config.enabled:
            return None
        url = f"{self.config.base_url}{path}"
        try:
            resp = httpx.patch(url, json=body, timeout=self.config.timeout)
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            logger.warning(f"[TraceChain] PATCH {path} failed: {exc}")
            return None

    # ── runs ──────────────────────────────────────────────────────────────────

    def create_run(
        self,
        workflow_name: str,
        input_payload: dict,
        metadata: Optional[dict] = None,
    ) -> Optional[str]:
        """Creates a workflow run. Returns run_id or None on failure."""
        data = self._post("/runs", {
            "workflow_name": workflow_name,
            "input_payload": input_payload,
            "metadata": metadata or {},
        })
        run_id = data.get("id") if data else None
        if run_id:
            logger.info(f"[TraceChain] Run started: {run_id} ({workflow_name})")
        else:
            logger.warning(f"[TraceChain] Could not create run for '{workflow_name}' - tracing disabled for this execution")
        return run_id

    def complete_run(
        self,
        run_id: str,
        output_payload: Any,
        total_cost: Optional[float] = None,
        total_tokens: Optional[int] = None,
    ) -> None:
        body: dict = {}
        if output_payload is not None:
            body["output_payload"] = _safe_json(output_payload)
        if total_cost is not None:
            body["total_cost"] = total_cost
        if total_tokens is not None:
            body["total_tokens"] = total_tokens
        self._post(f"/runs/{run_id}/complete", body)
        logger.info(f"[TraceChain] Run completed: {run_id}")

    def fail_run(self, run_id: str, error_message: str) -> None:
        self._post(f"/runs/{run_id}/fail", {"error_message": error_message})
        logger.warning(f"[TraceChain] Run failed: {run_id} - {error_message[:120]}")

    # ── steps ─────────────────────────────────────────────────────────────────

    def create_step(
        self,
        run_id: str,
        step_name: str,
        step_type: str,
        input_payload: dict,
        metadata: Optional[dict] = None,
    ) -> Optional[str]:
        data = self._post(f"/runs/{run_id}/steps", {
            "step_name": step_name,
            "step_type": step_type,
            "input_payload": _safe_json(input_payload),
            "metadata": metadata or {},
        })
        return data.get("id") if data else None

    def complete_step(
        self,
        run_id: str,
        step_id: str,
        output_payload: Any,
        duration_ms: int,
        retry_count: int = 0,
    ) -> None:
        self._post(f"/runs/{run_id}/steps/{step_id}/complete", {
            "output_payload": _safe_json(output_payload),
            "duration_ms": duration_ms,
            "retry_count": retry_count,
        })

    def fail_step(
        self,
        run_id: str,
        step_id: str,
        error_message: str,
        retry_count: int = 0,
    ) -> None:
        self._post(f"/runs/{run_id}/steps/{step_id}/fail", {
            "error_message": error_message,
            "retry_count": retry_count,
        })

    # ── llm calls ─────────────────────────────────────────────────────────────

    def log_llm_call(
        self,
        run_id: str,
        step_id: Optional[str],
        provider: str,
        model: str,
        prompt: str,
        response: Optional[str],
        input_tokens: Optional[int],
        output_tokens: Optional[int],
        total_tokens: Optional[int],
        estimated_cost: Optional[float],
        latency_ms: int,
        temperature: float,
        status: str,
        error_message: Optional[str] = None,
        prompt_version: Optional[str] = None,
        time_to_first_token_ms: Optional[int] = None,
        is_stream: bool = False,
    ) -> None:
        self._post(f"/runs/{run_id}/llm-calls", {
            "step_id": step_id,
            "provider": provider,
            "model": model,
            "prompt": prompt,
            "response": response,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
            "estimated_cost": estimated_cost,
            "latency_ms": latency_ms,
            "temperature": temperature,
            "status": status,
            "error_message": error_message,
            "prompt_version": prompt_version,
            "time_to_first_token_ms": time_to_first_token_ms,
            "is_stream": is_stream,
        })

    # ── evaluations ───────────────────────────────────────────────────────────

    def post_evaluation(self, run_id: str, scores: dict) -> None:
        self._post(f"/runs/{run_id}/evaluations", scores)
        logger.info(f"[TraceChain] Evaluation posted for run {run_id}")

    # ── replay ────────────────────────────────────────────────────────────────

    def trigger_replay(self, run_id: str) -> Optional[str]:
        data = self._post(f"/runs/{run_id}/replay", {})
        new_id = data.get("id") if data else None
        if new_id:
            logger.info(f"[TraceChain] Replay created: {new_id} (original: {run_id})")
        return new_id


# ── helpers ───────────────────────────────────────────────────────────────────

def _safe_json(value: Any) -> Any:
    """Convert any value to something JSON-serialisable."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {k: _safe_json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe_json(i) for i in value]
    return str(value)


# module-level default client — shared across all decorators
_default_client: Optional[TraceChainClient] = None


def get_default_client() -> TraceChainClient:
    global _default_client
    if _default_client is None:
        config = TraceChainConfig.default()
        if config.mode == "local":
            from .local_store import LocalClient
            _default_client = LocalClient(db_path=config.db_path)  # type: ignore[assignment]
        else:
            _default_client = TraceChainClient(config)
    return _default_client
