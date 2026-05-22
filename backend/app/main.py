import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import get_engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("tracechain")


def run_migrations():
    try:
        from alembic.config import Config
        from alembic import command
        alembic_cfg = Config("alembic.ini")
        command.upgrade(alembic_cfg, "head")
        logger.info("Database migrations applied.")
    except Exception as e:
        logger.warning(f"Alembic migration failed, falling back to create_all: {e}")
        from .models import Base as ModelBase  # noqa: F401 — registers all models
        ModelBase.metadata.create_all(bind=get_engine())


@asynccontextmanager
async def lifespan(app: FastAPI):
    run_migrations()
    logger.info("TraceChain backend started.")
    yield
    logger.info("TraceChain backend shutting down.")


app = FastAPI(
    title="TraceChain API",
    description="Reliability-first orchestration framework for LLM workflows",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ──────────────────────────────────────────────────────────────────
from .routes import health, runs, steps, llm_calls, prompts, evaluations, feedback, metrics  # noqa: E402
from .routes import ingest, graph, classifications, reliability, incidents, alerts  # noqa: E402
from .ws.manager import manager as ws_manager  # noqa: E402
from fastapi import WebSocket, WebSocketDisconnect, Query  # noqa: E402

app.include_router(health.router)
app.include_router(runs.router)
app.include_router(steps.router)
app.include_router(llm_calls.router)
app.include_router(prompts.router)
app.include_router(evaluations.router)
app.include_router(feedback.router)
app.include_router(metrics.router)
app.include_router(ingest.router)
app.include_router(graph.router)
app.include_router(classifications.router)
app.include_router(reliability.router)
app.include_router(incidents.router)
app.include_router(alerts.router)


@app.websocket("/ws/live")
async def websocket_live(
    ws: WebSocket,
    run_id: str = Query(None),
):
    """
    Real-time event stream. Connect to receive TraceEvents as they are ingested.
    Optional ?run_id=<id> filter to scope to a specific run.
    """
    await ws_manager.connect(ws, run_id_filter=run_id)
    try:
        await ws_manager.send_loop(ws)
    except WebSocketDisconnect:
        ws_manager.disconnect(ws)


@app.get("/")
def root():
    return {
        "name":    "TraceChain API",
        "version": "0.1.0",
        "docs":    "/docs",
        "ws":      "/ws/live",
        "ingest":  "/v1/ingest/batch",
    }
