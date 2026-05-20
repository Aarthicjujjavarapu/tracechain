"""
TraceChain SDK — reliability-first orchestration for LLM workflows.

Quick start:
    from tracechain import workflow, step, llm_step, evaluate_run

    @workflow(name="my_pipeline")
    def my_pipeline(query: str):
        docs   = retrieve(query)
        answer = generate(query, docs)
        evaluate_run(answer, query, docs)
        return answer

    @step(name="retrieve", retries=1)
    def retrieve(query: str) -> list[str]:
        return [...]

    @llm_step(name="generate", model="gpt-4o-mini", prompt_version="v1")
    def generate(query: str, docs: list[str]) -> str:
        return f"Answer using these docs: {query}\\n\\n{docs}"
"""
from .config import TraceChainConfig
from .client import TraceChainClient, get_default_client
from .local_store import LocalClient
from .workflow import workflow
from .steps import step
from .llm import llm_step
from .evals import evaluate_run, score as eval_score
from .replay import create_replay_metadata, trigger_replay
from .tracing import get_run_id, get_step_id
from .otel import configure_otel
from .observe import observe_llm

__all__ = [
    "TraceChainConfig",
    "TraceChainClient",
    "LocalClient",
    "get_default_client",
    "workflow",
    "step",
    "llm_step",
    "evaluate_run",
    "eval_score",
    "create_replay_metadata",
    "trigger_replay",
    "get_run_id",
    "get_step_id",
    "configure_otel",
    "observe_llm",
]

__version__ = "0.1.0"
