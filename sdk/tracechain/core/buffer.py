"""
Async-safe ring buffer with background flush.

Design goals:
- SDK instrumentation never blocks user code.
- Events are batched to reduce HTTP round-trips.
- If the exporter is slow, events are dropped (not queued forever) once the
  buffer is full — observability must not degrade the system being observed.
- Flush happens on a background thread (not asyncio) so it works from both
  sync and async user code without event-loop coupling.
"""
from __future__ import annotations

import atexit
import logging
import queue
import threading
from typing import TYPE_CHECKING, Callable, Optional

if TYPE_CHECKING:
    from .events import TraceEvent

logger = logging.getLogger("tracechain.buffer")

_DEFAULT_MAX_SIZE    = 10_000   # events
_DEFAULT_BATCH_SIZE  = 100
_DEFAULT_FLUSH_INTERVAL_S = 2.0


class EventBuffer:
    """
    Thread-safe ring buffer that flushes batches via a provided export function.

    Usage:
        def my_export(batch: list[TraceEvent]) -> None:
            requests.post("/ingest/batch", json=[e.to_dict() for e in batch])

        buf = EventBuffer(export_fn=my_export)
        buf.put(event)
        buf.shutdown()   # called automatically at process exit
    """

    def __init__(
        self,
        export_fn:          Callable[[list["TraceEvent"]], None],
        max_size:           int   = _DEFAULT_MAX_SIZE,
        batch_size:         int   = _DEFAULT_BATCH_SIZE,
        flush_interval_s:   float = _DEFAULT_FLUSH_INTERVAL_S,
    ) -> None:
        self._export_fn       = export_fn
        self._batch_size      = batch_size
        self._flush_interval  = flush_interval_s
        self._queue: queue.Queue["TraceEvent"] = queue.Queue(maxsize=max_size)
        self._dropped         = 0
        self._lock            = threading.Lock()
        self._shutdown        = threading.Event()
        self._thread          = threading.Thread(
            target=self._flush_loop,
            name="tracechain-buffer",
            daemon=True,
        )
        self._thread.start()
        atexit.register(self.shutdown)

    def put(self, event: "TraceEvent") -> None:
        try:
            self._queue.put_nowait(event)
        except queue.Full:
            with self._lock:
                self._dropped += 1
            logger.debug("TraceChain buffer full — event dropped (total dropped: %d)", self._dropped)

    def flush(self) -> None:
        """Drain the queue synchronously — useful in tests and at shutdown."""
        batch: list["TraceEvent"] = []
        while True:
            try:
                batch.append(self._queue.get_nowait())
                if len(batch) >= self._batch_size:
                    self._export(batch)
                    batch = []
            except queue.Empty:
                break
        if batch:
            self._export(batch)

    def shutdown(self, timeout: float = 5.0) -> None:
        self._shutdown.set()
        self._thread.join(timeout=timeout)
        self.flush()

    @property
    def dropped_count(self) -> int:
        with self._lock:
            return self._dropped

    # ── internal ──────────────────────────────────────────────────────────────

    def _flush_loop(self) -> None:
        while not self._shutdown.is_set():
            self._shutdown.wait(timeout=self._flush_interval)
            self.flush()

    def _export(self, batch: list["TraceEvent"]) -> None:
        try:
            self._export_fn(batch)
        except Exception:
            logger.debug("TraceChain exporter error — batch silently dropped", exc_info=True)
