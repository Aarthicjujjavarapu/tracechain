"""
Rule-based evaluation engine — no LLM calls, no external dependencies.

Scores are 0.0–1.0:
  relevance_score    — does the answer address the question?
  groundedness_score — is the answer supported by the retrieved documents?
  hallucination_risk — inverse of groundedness; high = answer strays from context
  quality_score      — holistic quality (length, coherence, grounding combined)

These scores are stored per run and displayed on the dashboard.
"""
import re
import logging
from typing import Optional

from .client import get_default_client
from .tracing import get_run_id

logger = logging.getLogger("tracechain.evals")


def _tokenize(text: str) -> set[str]:
    """Lowercase word tokens, stopwords removed."""
    STOPWORDS = {
        "a", "an", "the", "is", "it", "in", "on", "at", "to", "for",
        "of", "and", "or", "but", "not", "with", "this", "that", "be",
        "are", "was", "were", "has", "have", "had", "do", "does", "did",
        "i", "you", "he", "she", "we", "they", "my", "your", "its",
        "can", "will", "would", "could", "should", "may", "might",
    }
    tokens = set(re.findall(r"\b[a-z]{2,}\b", text.lower()))
    return tokens - STOPWORDS


def _jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _overlap_ratio(small: set, large: set) -> float:
    """What fraction of small's tokens appear in large?"""
    if not small:
        return 0.0
    return len(small & large) / len(small)


def score(
    answer: str,
    question: str,
    context_docs: Optional[list[str]] = None,
) -> dict:
    """
    Compute evaluation scores for an answer.

    Args:
        answer:       The LLM's response text.
        question:     The original user question.
        context_docs: Retrieved documents used to generate the answer.

    Returns dict with keys:
        relevance_score, groundedness_score, hallucination_risk,
        quality_score, failure_reason
    """
    failure_reason: Optional[str] = None

    # ── empty answer ──────────────────────────────────────────────────────────
    if not answer or not answer.strip():
        return {
            "relevance_score":    0.0,
            "groundedness_score": 0.0,
            "hallucination_risk": 1.0,
            "quality_score":      0.0,
            "failure_reason":     "Empty response from LLM",
        }

    answer_tokens   = _tokenize(answer)
    question_tokens = _tokenize(question)

    # ── relevance: how much of the question is addressed in the answer ────────
    relevance = _overlap_ratio(question_tokens, answer_tokens)
    # also factor in direct Jaccard similarity
    relevance = min(1.0, relevance * 0.7 + _jaccard(question_tokens, answer_tokens) * 0.3)

    # ── groundedness: how much of the answer is supported by the docs ─────────
    if context_docs:
        all_doc_tokens = _tokenize(" ".join(context_docs))
        groundedness = _overlap_ratio(answer_tokens, all_doc_tokens)
        groundedness = min(1.0, groundedness * 1.2)  # slight boost for overlap
    else:
        # no docs provided — can't assess groundedness
        groundedness = 0.5
        failure_reason = "No context documents provided for grounding check"

    hallucination_risk = max(0.0, 1.0 - groundedness)

    # ── quality: composite score ──────────────────────────────────────────────
    # Penalise very short answers (< 10 words)
    word_count = len(answer.split())
    length_score = min(1.0, word_count / 30)

    # Penalise answers that are just "I don't know" variants
    negative_phrases = ["i don't know", "i do not know", "cannot answer", "no information"]
    has_refusal = any(p in answer.lower() for p in negative_phrases)
    refusal_penalty = 0.3 if has_refusal else 0.0

    quality = (
        relevance    * 0.35 +
        groundedness * 0.35 +
        length_score * 0.20 +
        (1.0 - refusal_penalty) * 0.10
    ) - refusal_penalty * 0.1

    quality = max(0.0, min(1.0, quality))

    return {
        "relevance_score":    round(relevance, 4),
        "groundedness_score": round(groundedness, 4),
        "hallucination_risk": round(hallucination_risk, 4),
        "quality_score":      round(quality, 4),
        "failure_reason":     failure_reason,
    }


def evaluate_run(
    answer: str,
    question: str,
    context_docs: Optional[list[str]] = None,
    run_id: Optional[str] = None,
    client=None,
) -> dict:
    """
    Score an answer and POST the evaluation to the backend.

    If run_id is not provided, reads it from the current context (i.e., this
    was called inside a @workflow-decorated function).
    """
    scores = score(answer, question, context_docs)

    resolved_run_id = run_id or get_run_id()
    if resolved_run_id:
        tc = client or get_default_client()
        tc.post_evaluation(resolved_run_id, {
            "relevance_score":    scores["relevance_score"],
            "groundedness_score": scores["groundedness_score"],
            "hallucination_risk": scores["hallucination_risk"],
            "quality_score":      scores["quality_score"],
            "failure_reason":     scores["failure_reason"],
        })
    else:
        logger.warning("[TraceChain] evaluate_run called outside a @workflow context - scores not persisted")

    return scores
