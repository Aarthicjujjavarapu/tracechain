"""Tests for observe_retrieval() — RAG retrieval tracing context manager."""
import asyncio
from unittest.mock import MagicMock

import pytest

from tracechain.retrieval import observe_retrieval
from tracechain.tracing import set_run_id, reset_run_id


# ── helpers ───────────────────────────────────────────────────────────────────

def _mock_client(step_id="step-r1"):
    mc = MagicMock()
    mc.create_step.return_value   = step_id
    mc.complete_step.return_value  = None
    mc.fail_step.return_value      = None
    mc.post_evaluation.return_value = None
    return mc


def _run_ctx(run_id="run-1"):
    class _Ctx:
        def __enter__(self):
            self._tok = set_run_id(run_id)
            return self
        def __exit__(self, *_):
            reset_run_id(self._tok)
    return _Ctx()


# ── basic operation ───────────────────────────────────────────────────────────

class TestObserveRetrieval:
    def test_no_op_outside_workflow(self):
        mc = _mock_client()
        with observe_retrieval("docs", query="test", client=mc) as obs:
            obs.record(["doc1"])
        mc.create_step.assert_not_called()

    def test_creates_step_inside_run(self):
        mc = _mock_client()
        with _run_ctx():
            with observe_retrieval("docs", query="hello", client=mc) as obs:
                obs.record(["doc1", "doc2"])
        mc.create_step.assert_called_once()

    def test_step_name_contains_retrieve(self):
        """Step name must contain 'retriev' for RETRIEVAL_FAILURE classifier."""
        mc = _mock_client()
        with _run_ctx():
            with observe_retrieval("kb", query="q", client=mc) as obs:
                obs.record([])
        name = mc.create_step.call_args.kwargs["step_name"]
        assert "retriev" in name.lower()
        assert "kb" in name

    def test_step_name_default_when_no_name(self):
        mc = _mock_client()
        with _run_ctx():
            with observe_retrieval(query="q", client=mc) as obs:
                obs.record([])
        name = mc.create_step.call_args.kwargs["step_name"]
        assert name == "retrieve"

    def test_query_captured_in_input_payload(self):
        mc = _mock_client()
        with _run_ctx():
            with observe_retrieval("docs", query="what is AI?", k=5, client=mc) as obs:
                obs.record([])
        payload = mc.create_step.call_args.kwargs["input_payload"]
        assert payload["query"] == "what is AI?"
        assert payload["k"] == 5

    def test_complete_step_on_success(self):
        mc = _mock_client()
        with _run_ctx():
            with observe_retrieval("docs", query="q", client=mc) as obs:
                obs.record(["d1", "d2", "d3"])
        mc.complete_step.assert_called_once()
        mc.fail_step.assert_not_called()

    def test_fail_step_on_exception(self):
        mc = _mock_client()
        with _run_ctx():
            with pytest.raises(ConnectionError):
                with observe_retrieval("docs", query="q", client=mc):
                    raise ConnectionError("index unavailable")
        mc.fail_step.assert_called_once()
        assert "index unavailable" in mc.fail_step.call_args.kwargs["error_message"]

    def test_result_count_in_output(self):
        mc = _mock_client()
        docs = [f"doc{i}" for i in range(7)]
        with _run_ctx():
            with observe_retrieval("docs", query="q", client=mc) as obs:
                obs.record(docs)
        out = mc.complete_step.call_args.kwargs["output_payload"]
        assert out["result_count"] == 7

    def test_duration_ms_non_negative(self):
        mc = _mock_client()
        with _run_ctx():
            with observe_retrieval("docs", query="q", client=mc) as obs:
                obs.record([])
        assert mc.complete_step.call_args.kwargs["duration_ms"] >= 0


# ── relevance scores ──────────────────────────────────────────────────────────

class TestRelevanceScores:
    def test_no_evaluation_without_scores(self):
        mc = _mock_client()
        with _run_ctx():
            with observe_retrieval("docs", query="q", client=mc) as obs:
                obs.record(["doc1"])
        mc.post_evaluation.assert_not_called()

    def test_evaluation_posted_when_scores_given(self):
        mc = _mock_client()
        with _run_ctx():
            with observe_retrieval("docs", query="q", client=mc) as obs:
                obs.record(["d1", "d2", "d3"], relevance_scores=[0.9, 0.7, 0.5])
        mc.post_evaluation.assert_called_once()

    def test_relevance_score_is_mean(self):
        mc = _mock_client()
        with _run_ctx():
            with observe_retrieval("docs", query="q", client=mc) as obs:
                obs.record(["d1", "d2"], relevance_scores=[0.8, 0.6])
        ev = mc.post_evaluation.call_args[0][1]
        assert abs(ev["relevance_score"] - 0.7) < 0.01

    def test_scores_clamped_to_0_1(self):
        """Out-of-range scores (e.g. cosine similarity > 1) are clamped."""
        mc = _mock_client()
        with _run_ctx():
            with observe_retrieval("docs", query="q", client=mc) as obs:
                obs.record(["d1"], relevance_scores=[1.5, -0.2])
        ev = mc.post_evaluation.call_args[0][1]
        # clamped: [1.0, 0.0] → mean = 0.5
        assert ev["relevance_score"] == 0.5

    def test_avg_relevance_in_step_output(self):
        mc = _mock_client()
        with _run_ctx():
            with observe_retrieval("docs", query="q", client=mc) as obs:
                obs.record(["d1", "d2"], relevance_scores=[0.9, 0.7])
        out = mc.complete_step.call_args.kwargs["output_payload"]
        assert "relevance_scores" in out
        assert abs(out["avg_relevance"] - 0.8) < 0.01

    def test_no_evaluation_on_failure(self):
        """If retrieval raises, no evaluation should be posted."""
        mc = _mock_client()
        with _run_ctx():
            with pytest.raises(RuntimeError):
                with observe_retrieval("docs", query="q", client=mc) as obs:
                    obs.record(["d1"], relevance_scores=[0.9])
                    raise RuntimeError("search failed")
        mc.post_evaluation.assert_not_called()

    def test_docs_capped_in_output(self):
        """Output payload should store at most 5 docs to avoid huge payloads."""
        mc = _mock_client()
        big_docs = [f"doc{i}" for i in range(20)]
        with _run_ctx():
            with observe_retrieval("docs", query="q", client=mc) as obs:
                obs.record(big_docs, relevance_scores=[0.5] * 20)
        out = mc.complete_step.call_args.kwargs["output_payload"]
        assert len(out["docs"]) <= 5
        assert out["result_count"] == 20


# ── single doc (not a list) ───────────────────────────────────────────────────

class TestSingleDoc:
    def test_single_string_doc_wrapped_in_list(self):
        mc = _mock_client()
        with _run_ctx():
            with observe_retrieval("docs", query="q", client=mc) as obs:
                obs.record("just one doc")
        out = mc.complete_step.call_args.kwargs["output_payload"]
        assert out["result_count"] == 1


# ── async ────────────────────────────────────────────────────────────────────

class TestAsync:
    def test_async_success(self):
        mc = _mock_client()

        async def run():
            with _run_ctx():
                async with observe_retrieval("docs", query="async q", client=mc) as obs:
                    obs.record(["d1"], relevance_scores=[0.85])

        asyncio.run(run())
        mc.complete_step.assert_called_once()
        mc.post_evaluation.assert_called_once()

    def test_async_failure(self):
        mc = _mock_client()

        async def run():
            with _run_ctx():
                with pytest.raises(TimeoutError):
                    async with observe_retrieval("docs", query="q", client=mc):
                        raise TimeoutError("search timeout")

        asyncio.run(run())
        mc.fail_step.assert_called_once()
        mc.post_evaluation.assert_not_called()
