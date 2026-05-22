"""
LocalClient — zero-infrastructure tracing backed by SQLite.

Activated automatically when TRACECHAIN_MODE=local is set, or by passing
a LocalClient instance directly to any decorator:

    from tracechain import LocalClient, workflow, step

    client = LocalClient()          # writes to ./tracechain.db
    client = LocalClient("my.db")  # custom path

    @workflow(name="pipeline", client=client)
    def pipeline(query: str):
        ...

The schema mirrors the backend PostgreSQL schema so traces can be migrated
to the full backend later with zero code changes.
"""
import json
import logging
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from .client import _safe_json

logger = logging.getLogger("tracechain.local")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS workflow_runs (
    id               TEXT PRIMARY KEY,
    workflow_name    TEXT NOT NULL,
    status           TEXT NOT NULL DEFAULT 'pending',
    input_payload    TEXT NOT NULL DEFAULT '{}',
    output_payload   TEXT,
    error_message    TEXT,
    started_at       TEXT NOT NULL,
    ended_at         TEXT,
    duration_ms      INTEGER,
    total_cost       REAL,
    total_tokens     INTEGER,
    original_run_id  TEXT,
    is_replay        INTEGER NOT NULL DEFAULT 0,
    metadata         TEXT
);

CREATE TABLE IF NOT EXISTS trace_steps (
    id             TEXT PRIMARY KEY,
    run_id         TEXT NOT NULL,
    step_name      TEXT NOT NULL,
    step_type      TEXT NOT NULL DEFAULT 'step',
    status         TEXT NOT NULL DEFAULT 'pending',
    input_payload  TEXT NOT NULL DEFAULT '{}',
    output_payload TEXT,
    error_message  TEXT,
    started_at     TEXT NOT NULL,
    ended_at       TEXT,
    duration_ms    INTEGER,
    retry_count    INTEGER NOT NULL DEFAULT 0,
    metadata       TEXT
);

CREATE TABLE IF NOT EXISTS llm_calls (
    id                     TEXT PRIMARY KEY,
    run_id                 TEXT NOT NULL,
    step_id                TEXT,
    provider               TEXT NOT NULL DEFAULT 'openai',
    model                  TEXT NOT NULL,
    prompt                 TEXT NOT NULL,
    response               TEXT,
    input_tokens           INTEGER,
    output_tokens          INTEGER,
    total_tokens           INTEGER,
    estimated_cost         REAL,
    latency_ms             INTEGER,
    time_to_first_token_ms INTEGER,
    is_stream              INTEGER NOT NULL DEFAULT 0,
    temperature            REAL,
    status                 TEXT NOT NULL DEFAULT 'success',
    error_message          TEXT,
    prompt_version         TEXT,
    created_at             TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS evaluation_results (
    id                 TEXT PRIMARY KEY,
    run_id             TEXT NOT NULL,
    relevance_score    REAL NOT NULL DEFAULT 0.0,
    groundedness_score REAL NOT NULL DEFAULT 0.0,
    hallucination_risk REAL NOT NULL DEFAULT 0.0,
    quality_score      REAL NOT NULL DEFAULT 0.0,
    failure_reason     TEXT,
    created_at         TEXT NOT NULL
);
"""


def _uid() -> str:
    return str(uuid.uuid4())


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ms_since(iso: str) -> Optional[int]:
    """Return elapsed milliseconds since an ISO timestamp, or None on parse error."""
    try:
        started = datetime.fromisoformat(iso)
        return int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
    except Exception:
        return None


class LocalClient:
    """
    Drop-in replacement for TraceChainClient that writes traces to SQLite.
    Requires no server, no database server, no network. Uses Python's
    built-in sqlite3 module — no additional dependencies.

    Thread-safe: each thread gets its own SQLite connection via threading.local.
    """

    def __init__(self, db_path: str = "./tracechain.db"):
        self.db_path = db_path
        self._local  = threading.local()
        self._setup()
        logger.info(f"[TraceChain:local] Tracing to {db_path}")

    # ── connection management ──────────────────────────────────────────────────

    def _conn(self) -> sqlite3.Connection:
        """Return (or create) this thread's SQLite connection."""
        if not hasattr(self._local, "conn"):
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")  # better concurrent write perf
            self._local.conn = conn
        return self._local.conn

    def _setup(self) -> None:
        self._conn().executescript(_SCHEMA)
        self._conn().commit()

    def _run(self, sql: str, params: tuple = ()) -> None:
        """Execute a write statement."""
        try:
            self._conn().execute(sql, params)
            self._conn().commit()
        except Exception as exc:
            logger.warning(f"[TraceChain:local] DB write failed: {exc}")

    # ── runs ──────────────────────────────────────────────────────────────────

    def create_run(
        self,
        workflow_name: str,
        input_payload: dict,
        metadata: Optional[dict] = None,
    ) -> Optional[str]:
        run_id = _uid()
        try:
            self._run(
                "INSERT INTO workflow_runs "
                "(id, workflow_name, status, input_payload, started_at, metadata) "
                "VALUES (?, ?, 'running', ?, ?, ?)",
                (run_id, workflow_name,
                 json.dumps(input_payload or {}), _now(),
                 json.dumps(metadata) if metadata else None),
            )
            logger.info(f"[TraceChain:local] Run started: {run_id} ({workflow_name})")
            return run_id
        except Exception as exc:
            logger.warning(f"[TraceChain:local] create_run failed: {exc}")
            return None

    def complete_run(
        self,
        run_id: str,
        output_payload: Any,
        total_cost: Optional[float] = None,
        total_tokens: Optional[int] = None,
    ) -> None:
        row = self._conn().execute(
            "SELECT started_at FROM workflow_runs WHERE id = ?", (run_id,)
        ).fetchone()
        duration_ms = _ms_since(row["started_at"]) if row else None
        self._run(
            "UPDATE workflow_runs "
            "SET status='success', output_payload=?, ended_at=?, "
            "    duration_ms=?, total_cost=?, total_tokens=? "
            "WHERE id=?",
            (json.dumps(_safe_json(output_payload)), _now(),
             duration_ms, total_cost, total_tokens, run_id),
        )
        logger.info(f"[TraceChain:local] Run completed: {run_id}")

    def fail_run(self, run_id: str, error_message: str) -> None:
        self._run(
            "UPDATE workflow_runs SET status='failed', error_message=?, ended_at=? WHERE id=?",
            (error_message, _now(), run_id),
        )
        logger.warning(f"[TraceChain:local] Run failed: {run_id}")

    # ── steps ─────────────────────────────────────────────────────────────────

    def create_step(
        self,
        run_id: str,
        step_name: str,
        step_type: str,
        input_payload: dict,
        metadata: Optional[dict] = None,
    ) -> Optional[str]:
        step_id = _uid()
        self._run(
            "INSERT INTO trace_steps "
            "(id, run_id, step_name, step_type, status, input_payload, started_at, metadata) "
            "VALUES (?, ?, ?, ?, 'running', ?, ?, ?)",
            (step_id, run_id, step_name, step_type,
             json.dumps(_safe_json(input_payload or {})), _now(),
             json.dumps(metadata) if metadata else None),
        )
        return step_id

    def complete_step(
        self,
        run_id: str,
        step_id: str,
        output_payload: Any,
        duration_ms: int,
        retry_count: int = 0,
    ) -> None:
        self._run(
            "UPDATE trace_steps "
            "SET status='success', output_payload=?, duration_ms=?, retry_count=?, ended_at=? "
            "WHERE id=?",
            (json.dumps(_safe_json(output_payload)), duration_ms, retry_count, _now(), step_id),
        )

    def fail_step(
        self,
        run_id: str,
        step_id: str,
        error_message: str,
        retry_count: int = 0,
    ) -> None:
        self._run(
            "UPDATE trace_steps "
            "SET status='failed', error_message=?, retry_count=?, ended_at=? "
            "WHERE id=?",
            (error_message, retry_count, _now(), step_id),
        )

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
        self._run(
            "INSERT INTO llm_calls "
            "(id, run_id, step_id, provider, model, prompt, response, "
            " input_tokens, output_tokens, total_tokens, estimated_cost, "
            " latency_ms, time_to_first_token_ms, is_stream, temperature, "
            " status, error_message, prompt_version, created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                _uid(), run_id, step_id, provider, model, prompt, response,
                input_tokens, output_tokens, total_tokens, estimated_cost,
                latency_ms, time_to_first_token_ms, int(is_stream), temperature,
                status, error_message, prompt_version, _now(),
            ),
        )

    # ── evaluations ───────────────────────────────────────────────────────────

    def post_evaluation(self, run_id: str, scores: dict) -> None:
        self._run(
            "INSERT INTO evaluation_results "
            "(id, run_id, relevance_score, groundedness_score, "
            " hallucination_risk, quality_score, failure_reason, created_at) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (
                _uid(), run_id,
                scores.get("relevance_score",    0.0),
                scores.get("groundedness_score", 0.0),
                scores.get("hallucination_risk", 0.0),
                scores.get("quality_score",      0.0),
                scores.get("failure_reason"),
                _now(),
            ),
        )

    # ── replay ────────────────────────────────────────────────────────────────

    def trigger_replay(self, run_id: str) -> Optional[str]:
        row = self._conn().execute(
            "SELECT workflow_name, input_payload, metadata FROM workflow_runs WHERE id=?",
            (run_id,),
        ).fetchone()
        if not row:
            return None
        new_id = _uid()
        self._run(
            "INSERT INTO workflow_runs "
            "(id, workflow_name, status, input_payload, started_at, original_run_id, is_replay, metadata) "
            "VALUES (?,?,'pending',?,?,?,1,?)",
            (new_id, row["workflow_name"], row["input_payload"], _now(), run_id, row["metadata"]),
        )
        logger.info(f"[TraceChain:local] Replay created: {new_id} (original: {run_id})")
        return new_id

    # ── read helpers ──────────────────────────────────────────────────────────

    def get_run(self, run_id: str) -> Optional[dict]:
        row = self._conn().execute(
            "SELECT * FROM workflow_runs WHERE id=?", (run_id,)
        ).fetchone()
        return dict(row) if row else None

    def get_runs(self, limit: int = 100) -> list[dict]:
        rows = self._conn().execute(
            "SELECT * FROM workflow_runs ORDER BY started_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]

    def get_steps(self, run_id: str) -> list[dict]:
        rows = self._conn().execute(
            "SELECT * FROM trace_steps WHERE run_id=? ORDER BY started_at", (run_id,)
        ).fetchall()
        return [dict(r) for r in rows]

    def get_llm_calls(self, run_id: str) -> list[dict]:
        rows = self._conn().execute(
            "SELECT * FROM llm_calls WHERE run_id=? ORDER BY created_at", (run_id,)
        ).fetchall()
        return [dict(r) for r in rows]
