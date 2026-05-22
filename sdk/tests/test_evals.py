import pytest
from tracechain.evals import score


# ── helpers ───────────────────────────────────────────────────────────────────

def _score(answer, question="what is tracechain", docs=None):
    return score(answer, question, docs)


# ── empty / degenerate inputs ─────────────────────────────────────────────────

def test_empty_answer_returns_zeros():
    s = _score("")
    assert s["relevance_score"]    == 0.0
    assert s["groundedness_score"] == 0.0
    assert s["hallucination_risk"] == 1.0
    assert s["quality_score"]      == 0.0
    assert s["failure_reason"] is not None


def test_whitespace_only_answer_treated_as_empty():
    s = _score("   \n\t  ")
    assert s["quality_score"] == 0.0


# ── scores are always bounded ─────────────────────────────────────────────────

def test_scores_bounded_0_to_1():
    s = _score(
        "TraceChain is an observability framework for LLM workflows that traces every step.",
        question="what is tracechain",
        docs=["TraceChain traces LLM workflows and provides observability tools."],
    )
    for key in ("relevance_score", "groundedness_score", "hallucination_risk", "quality_score"):
        assert 0.0 <= s[key] <= 1.0, f"{key} out of bounds: {s[key]}"


# ── relevance ─────────────────────────────────────────────────────────────────

def test_relevant_answer_scores_higher_than_irrelevant():
    question = "how does replay work in tracechain"
    relevant = _score(
        "Replay works by copying the original run input and creating a new run marked is_replay=True.",
        question=question,
    )
    irrelevant = _score(
        "The weather today is sunny and warm.",
        question=question,
    )
    assert relevant["relevance_score"] > irrelevant["relevance_score"]


# ── groundedness / hallucination ──────────────────────────────────────────────

def test_no_context_docs_sets_groundedness_to_half():
    s = _score("Some answer about something.", docs=None)
    assert s["groundedness_score"] == 0.5
    assert s["failure_reason"] is not None


def test_grounded_answer_has_low_hallucination_risk():
    docs = ["TraceChain uses Python decorators to trace workflow steps automatically."]
    s = score(
        "TraceChain uses Python decorators to trace workflow steps.",
        question="how does tracechain work",
        context_docs=docs,
    )
    assert s["groundedness_score"] > 0.5
    assert s["hallucination_risk"] < 0.5


def test_hallucination_risk_equals_1_minus_groundedness():
    docs = ["Some context document about tracechain."]
    s = score("tracechain context document", "question", context_docs=docs)
    assert abs(s["hallucination_risk"] - (1.0 - s["groundedness_score"])) < 1e-6


# ── quality ───────────────────────────────────────────────────────────────────

def test_short_answer_penalised():
    long_answer  = _score("TraceChain is a reliability-first observability framework for LLM workflows " * 3)
    short_answer = _score("yes")
    assert long_answer["quality_score"] > short_answer["quality_score"]


def test_refusal_phrase_penalised():
    normal  = _score("TraceChain provides tracing, evaluation, and replay for LLM workflows.")
    refusal = _score("I don't know the answer to that question about tracechain workflows.")
    assert normal["quality_score"] > refusal["quality_score"]


def test_quality_is_composite_of_relevance_and_groundedness():
    docs = ["TraceChain traces every step of an LLM workflow automatically."]
    s = score(
        "TraceChain automatically traces every step of an LLM workflow pipeline.",
        question="how does tracechain trace workflows",
        context_docs=docs,
    )
    # A high-quality answer should score above 0.5
    assert s["quality_score"] > 0.5


# ── failure_reason ────────────────────────────────────────────────────────────

def test_failure_reason_none_for_good_answer():
    docs = ["TraceChain is an observability tool."]
    s = score("TraceChain is an observability tool.", "what is tracechain", context_docs=docs)
    assert s["failure_reason"] is None
