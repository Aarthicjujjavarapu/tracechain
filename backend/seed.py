"""
Seed the database with realistic demo data so the dashboard has something to show.
Run: python seed.py  (from the backend/ directory with DATABASE_URL set)
"""
import uuid
import random
from datetime import datetime, timezone, timedelta
from app.database import get_session_factory, get_engine
from app.models import (
    Base, WorkflowRun, TraceStep, LLMCall, PromptVersion,
    EvaluationResult, HumanFeedback,
    RunStatus, StepType, LLMStatus,
)

MODELS = ["gpt-4o-mini", "gpt-4o", "gpt-4-turbo"]
WORKFLOWS = ["customer_support_agent", "document_qa_agent", "content_moderation", "summarization_pipeline"]
STEPS = {
    "customer_support_agent": ["retrieve_docs", "generate_answer", "validate_answer"],
    "document_qa_agent": ["search_documents", "generate_answer", "evaluate_groundedness"],
    "content_moderation": ["extract_content", "classify_content", "flag_review"],
    "summarization_pipeline": ["chunk_text", "summarize_chunks", "merge_summaries"],
}

COST_MAP = {
    "gpt-4o-mini": (0.00015, 0.00060),   # input/output per 1k tokens
    "gpt-4o":      (0.005,   0.015),
    "gpt-4-turbo": (0.01,    0.03),
}

SAMPLE_PROMPTS = [
    {
        "prompt_name": "support_answer_prompt",
        "version": "v1",
        "prompt_text": "You are a helpful customer support agent. Answer the following question using the provided documents.\n\nQuestion: {query}\n\nDocuments:\n{docs}\n\nAnswer:",
        "is_active": False,
    },
    {
        "prompt_name": "support_answer_prompt",
        "version": "v2",
        "prompt_text": "You are a concise, accurate customer support agent. Use only the provided documents to answer.\n\nQuestion: {query}\n\nContext:\n{docs}\n\nProvide a direct, helpful answer:",
        "is_active": True,
    },
    {
        "prompt_name": "document_qa_prompt",
        "version": "v1",
        "prompt_text": "Answer the question based on the documents provided.\n\nQuestion: {question}\nDocuments: {docs}\nAnswer:",
        "is_active": True,
    },
    {
        "prompt_name": "summarization_prompt",
        "version": "v1",
        "prompt_text": "Summarize the following text in 2-3 sentences:\n\n{text}",
        "is_active": True,
    },
]

SAMPLE_QUESTIONS = [
    "How do I reset my password?",
    "What is your refund policy?",
    "How can I upgrade my subscription?",
    "Why is my payment failing?",
    "Can I use the product on multiple devices?",
    "How do I export my data?",
    "What are the system requirements?",
    "How do I contact support?",
]


def _rand_duration(min_ms=100, max_ms=3000):
    return random.randint(min_ms, max_ms)


def _rand_tokens(model):
    input_t = random.randint(80, 600)
    output_t = random.randint(40, 300)
    return input_t, output_t


def _calc_cost(model, input_t, output_t):
    in_rate, out_rate = COST_MAP.get(model, (0.001, 0.002))
    return round((input_t / 1000 * in_rate) + (output_t / 1000 * out_rate), 6)


def _rand_time(days_ago_max=30):
    delta = timedelta(
        days=random.randint(0, days_ago_max),
        hours=random.randint(0, 23),
        minutes=random.randint(0, 59),
    )
    return datetime.now(timezone.utc) - delta


def seed():
    db = get_session_factory()()
    try:
        # ── Prompts ──────────────────────────────────────────────────────────
        print("Seeding prompt versions...")
        prompt_records = []
        for p in SAMPLE_PROMPTS:
            pv = PromptVersion(
                id=str(uuid.uuid4()),
                prompt_name=p["prompt_name"],
                version=p["version"],
                prompt_text=p["prompt_text"],
                is_active=p["is_active"],
                created_at=_rand_time(60),
            )
            db.add(pv)
            prompt_records.append(pv)
        db.flush()

        # ── Workflow Runs ────────────────────────────────────────────────────
        print("Seeding workflow runs...")
        run_records = []
        for i in range(60):
            wf = random.choice(WORKFLOWS)
            model = random.choice(MODELS)
            question = random.choice(SAMPLE_QUESTIONS)
            started = _rand_time(30)
            duration = _rand_duration(200, 4000)
            ended = started + timedelta(milliseconds=duration)
            # ~85% success rate
            status = RunStatus.success if random.random() < 0.85 else RunStatus.failed
            is_replay = random.random() < 0.1

            run = WorkflowRun(
                id=str(uuid.uuid4()),
                workflow_name=wf,
                status=status,
                input_payload={"query": question},
                output_payload={"answer": f"Sample answer for: {question}", "grounded": True} if status == RunStatus.success else None,
                error_message="OpenAI API timeout after 30s" if status == RunStatus.failed else None,
                started_at=started,
                ended_at=ended,
                duration_ms=duration,
                is_replay=is_replay,
                metadata_={"source": "seed"},
            )

            # total tokens + cost accumulated from llm calls
            total_tokens = 0
            total_cost = 0.0

            db.add(run)
            db.flush()

            # ── Trace Steps ──────────────────────────────────────────────────
            step_names = STEPS[wf]
            step_start = started
            for j, sname in enumerate(step_names):
                s_duration = _rand_duration(50, 1200)
                s_end = step_start + timedelta(milliseconds=s_duration)
                # last step fails on failed runs
                s_status = RunStatus.failed if (status == RunStatus.failed and j == len(step_names) - 1) else RunStatus.success
                stype = StepType.llm_step if "generate" in sname or "summarize" in sname else StepType.step

                ts = TraceStep(
                    id=str(uuid.uuid4()),
                    run_id=run.id,
                    step_name=sname,
                    step_type=stype,
                    status=s_status,
                    input_payload={"query": question},
                    output_payload={"result": f"output of {sname}"} if s_status == RunStatus.success else None,
                    error_message="Timeout" if s_status == RunStatus.failed else None,
                    started_at=step_start,
                    ended_at=s_end,
                    duration_ms=s_duration,
                    retry_count=random.randint(0, 1),
                )
                db.add(ts)
                db.flush()

                # ── LLM Call (only for llm_step) ─────────────────────────────
                if stype == StepType.llm_step:
                    in_t, out_t = _rand_tokens(model)
                    cost = _calc_cost(model, in_t, out_t)
                    total_tokens += in_t + out_t
                    total_cost += cost

                    llm = LLMCall(
                        id=str(uuid.uuid4()),
                        run_id=run.id,
                        step_id=ts.id,
                        provider="openai",
                        model=model,
                        prompt=f"Answer this question using these docs: {question} [doc1] [doc2]",
                        response=f"Based on the provided documents, {question.lower()} The answer is..." if s_status == RunStatus.success else None,
                        input_tokens=in_t,
                        output_tokens=out_t,
                        total_tokens=in_t + out_t,
                        estimated_cost=cost,
                        latency_ms=_rand_duration(300, 2000),
                        temperature=0.7,
                        status=LLMStatus.success if s_status == RunStatus.success else LLMStatus.failed,
                        error_message=None if s_status == RunStatus.success else "Rate limit exceeded",
                        prompt_version="v2" if wf == "customer_support_agent" else "v1",
                        created_at=step_start,
                    )
                    db.add(llm)

                step_start = s_end

            # update run totals
            run.total_tokens = total_tokens or None
            run.total_cost = round(total_cost, 6) or None

            # ── Evaluation ───────────────────────────────────────────────────
            if status == RunStatus.success:
                ev = EvaluationResult(
                    id=str(uuid.uuid4()),
                    run_id=run.id,
                    relevance_score=round(random.uniform(0.6, 1.0), 3),
                    groundedness_score=round(random.uniform(0.5, 1.0), 3),
                    hallucination_risk=round(random.uniform(0.0, 0.4), 3),
                    quality_score=round(random.uniform(0.55, 1.0), 3),
                    created_at=ended,
                )
                db.add(ev)

            # ── Human Feedback (30% of runs) ─────────────────────────────────
            if random.random() < 0.3:
                comments = [
                    "Very accurate response",
                    "Could be more concise",
                    "Missed the main point",
                    "Helpful and clear",
                    None,
                ]
                fb = HumanFeedback(
                    id=str(uuid.uuid4()),
                    run_id=run.id,
                    rating=random.randint(3, 5) if status == RunStatus.success else random.randint(1, 3),
                    comment=random.choice(comments),
                    created_at=ended + timedelta(minutes=random.randint(1, 60)),
                )
                db.add(fb)

            run_records.append(run)

        db.commit()
        print(f"Seeded {len(run_records)} workflow runs with steps, LLM calls, evaluations, and feedback.")
        print(f"Seeded {len(prompt_records)} prompt versions.")
        print("Done.")

    except Exception as e:
        db.rollback()
        print(f"Seed failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
