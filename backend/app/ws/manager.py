"""
WebSocket connection manager for real-time trace streaming.

Clients connect to /ws/live and receive JSON-encoded TraceEvent payloads
as they are ingested. Clients can filter by run_id via query param.

Design:
- One asyncio.Queue per connected client.
- Broadcast fans out to all queues; filtering happens per-client so
  the broadcast path stays O(clients) without per-event filtering overhead.
- Stale/disconnected clients are pruned lazily on next broadcast.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

from fastapi import WebSocket

logger = logging.getLogger("tracechain.ws")


class ConnectionManager:
    def __init__(self) -> None:
        # map of websocket → (queue, optional run_id filter)
        self._clients: dict[WebSocket, tuple[asyncio.Queue, Optional[str]]] = {}
        # The running event loop — set once at startup so sync code can broadcast
        self._loop: asyncio.AbstractEventLoop | None = None

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    async def connect(self, ws: WebSocket, run_id_filter: Optional[str] = None) -> None:
        await ws.accept()
        self._clients[ws] = (asyncio.Queue(maxsize=1000), run_id_filter)
        logger.debug("WS client connected (filter=%s, total=%d)", run_id_filter, len(self._clients))

    def disconnect(self, ws: WebSocket) -> None:
        self._clients.pop(ws, None)
        logger.debug("WS client disconnected (total=%d)", len(self._clients))

    async def broadcast(self, event: dict) -> None:
        """Fan out event to all connected clients that match the filter."""
        event_run_id = event.get("run_id")
        dead: list[WebSocket] = []

        for ws, (q, run_filter) in self._clients.items():
            if run_filter and run_filter != event_run_id:
                continue
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                logger.debug("WS queue full for client — dropping event")

        for ws in dead:
            self.disconnect(ws)

    async def send_loop(self, ws: WebSocket) -> None:
        """
        Per-client send loop — runs until the client disconnects.
        Call this from the websocket route handler.
        """
        q, _ = self._clients[ws]
        try:
            while True:
                event = await q.get()
                await ws.send_json(event)
        except Exception:
            self.disconnect(ws)


    def fire_event_sync(self, event: dict) -> None:
        """Thread-safe fire-and-forget broadcast from synchronous route handlers.

        FastAPI runs sync routes in a thread pool; asyncio.run_coroutine_threadsafe
        schedules the coroutine onto the main uvicorn event loop safely.
        """
        if self._loop and self._loop.is_running():
            try:
                asyncio.run_coroutine_threadsafe(self.broadcast(event), self._loop)
            except Exception:
                pass


# Singleton — shared across the FastAPI app via dependency injection
manager = ConnectionManager()
