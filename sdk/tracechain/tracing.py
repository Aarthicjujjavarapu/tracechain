"""
Context propagation — stores run_id and step_id in Python contextvars so they
flow automatically down the call stack without the user passing them explicitly.
Works correctly across threads because each thread gets its own context copy.
"""
from contextvars import ContextVar
from typing import Optional

_current_run_id:  ContextVar[Optional[str]] = ContextVar("tracechain_run_id",  default=None)
_current_step_id: ContextVar[Optional[str]] = ContextVar("tracechain_step_id", default=None)

# accumulated cost + tokens for the current run (reset per workflow invocation)
_run_total_cost:   ContextVar[float] = ContextVar("tracechain_run_cost",   default=0.0)
_run_total_tokens: ContextVar[int]   = ContextVar("tracechain_run_tokens", default=0)


def get_run_id()  -> Optional[str]: return _current_run_id.get()
def get_step_id() -> Optional[str]: return _current_step_id.get()

def set_run_id(run_id: str):   return _current_run_id.set(run_id)
def set_step_id(step_id: str): return _current_step_id.set(step_id)

def reset_run_id(token):   _current_run_id.reset(token)
def reset_step_id(token):  _current_step_id.reset(token)

def get_run_totals() -> tuple[float, int]:
    return _run_total_cost.get(), _run_total_tokens.get()

def add_llm_usage(cost: float, tokens: int) -> None:
    _run_total_cost.set(_run_total_cost.get() + cost)
    _run_total_tokens.set(_run_total_tokens.get() + tokens)

def reset_run_totals() -> None:
    _run_total_cost.set(0.0)
    _run_total_tokens.set(0)
