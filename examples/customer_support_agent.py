"""
TraceChain Example 1 — Customer Support Agent
==============================================
A multi-step agent that answers customer support questions using a
fake knowledge base, then evaluates and traces every step.

Run:
    # from the repo root
    pip install -e sdk/
    python examples/customer_support_agent.py

    # with a specific question
    python examples/customer_support_agent.py "How do I cancel my subscription?"

    # with a real OpenAI key
    OPENAI_API_KEY=sk-... python examples/customer_support_agent.py
"""
import sys
import os
import json

# allow running from the repo root without installing the package
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "sdk"))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from tracechain import workflow, step, llm_step, evaluate_run, get_run_id

# -- Knowledge base ------------------------------------------------------------
# In a real system this would be a vector store.  We keep it simple.

KNOWLEDGE_BASE = {
    "password": [
        "To reset your password, go to the login page and click 'Forgot Password'. Enter your registered email address. You will receive a password reset link within 5 minutes.",
        "Passwords must be at least 8 characters and contain one uppercase letter, one number, and one special character.",
        "If you do not receive the password reset email, check your spam folder or contact support at help@example.com.",
    ],
    "billing": [
        "We accept Visa, Mastercard, American Express, and PayPal. All payments are processed securely via Stripe.",
        "Invoices are sent automatically on the 1st of each month to your registered billing email.",
        "To update your payment method, navigate to Account Settings > Billing > Payment Methods.",
    ],
    "subscription": [
        "You can upgrade or downgrade your plan at any time from Account Settings > Subscription.",
        "To cancel your subscription, go to Account Settings > Subscription > Cancel Plan. Your access continues until the end of the billing period.",
        "Refunds are available within 14 days of the initial purchase for annual plans. Monthly plans are non-refundable.",
    ],
    "devices": [
        "You can use the product on up to 5 devices simultaneously with a Pro plan.",
        "To add a new device, log in from that device. Devices over the limit will be prompted to sign out of another session.",
        "Device management is available under Account Settings > Devices.",
    ],
    "export": [
        "To export your data, go to Account Settings > Data > Export. Choose CSV or JSON format.",
        "Data exports are processed within 24 hours and sent to your email as a download link.",
        "You can schedule automatic weekly data exports from the Settings panel.",
    ],
    "default": [
        "Our support team is available Monday to Friday, 9 AM to 6 PM EST.",
        "You can reach us at help@example.com or via live chat on our website.",
        "For urgent issues, please call our support hotline at 1-800-555-0123.",
    ],
}


def _keyword_lookup(query: str) -> list[str]:
    """Return knowledge base docs matching keywords in the query."""
    query_lower = query.lower()
    matched = []
    for topic, docs in KNOWLEDGE_BASE.items():
        if topic in query_lower or any(
            keyword in query_lower
            for keyword in {
                "password": ["reset", "forgot", "login", "sign in"],
                "billing":  ["invoice", "payment", "charge", "credit card"],
                "subscription": ["cancel", "upgrade", "downgrade", "plan", "refund"],
                "devices": ["device", "laptop", "phone", "multiple"],
                "export": ["export", "download", "data", "backup"],
            }.get(topic, [topic])
        ):
            matched.extend(docs)

    return matched[:3] if matched else KNOWLEDGE_BASE["default"][:3]


# -- Workflow steps -------------------------------------------------------------

@step(name="retrieve_docs", retries=1)
def retrieve_docs(query: str) -> list[str]:
    """Retrieve relevant support documentation for the query."""
    docs = _keyword_lookup(query)
    print(f"  [retrieve_docs] Found {len(docs)} relevant document(s)")
    return docs


@llm_step(name="generate_answer", model="gpt-4o-mini", prompt_version="v2")
def generate_answer(query: str, docs: list[str]) -> str:
    """Build a prompt from the query and retrieved docs."""
    formatted_docs = "\n".join(f"  - {doc}" for doc in docs)
    return (
        f"You are a helpful customer support agent. Answer the customer's question "
        f"accurately and concisely using only the provided documentation.\n\n"
        f"Customer question: {query}\n\n"
        f"Relevant documentation:\n{formatted_docs}\n\n"
        f"Provide a clear, helpful answer in 2-3 sentences:"
    )


@step(name="validate_answer", retries=1)
def validate_answer(answer: str, docs: list[str]) -> dict:
    """Check basic quality requirements before returning to customer."""
    word_count = len(answer.split())
    is_too_short = word_count < 10
    contains_doc_terms = any(
        word in answer.lower()
        for doc in docs
        for word in doc.lower().split()
        if len(word) > 5
    )

    if is_too_short:
        raise ValueError(f"Answer too short ({word_count} words) — regeneration required")

    return {
        "answer": answer,
        "word_count": word_count,
        "grounded": contains_doc_terms,
        "passed_validation": True,
    }


# -- Main workflow --------------------------------------------------------------

@workflow(name="customer_support_agent")
def support_agent(query: str) -> dict:
    """Full customer support pipeline: retrieve → generate → validate → evaluate."""
    print(f"\n{'-'*60}")
    print(f"  Query: {query}")
    print(f"{'-'*60}")

    docs      = retrieve_docs(query)
    answer    = generate_answer(query, docs)
    validated = validate_answer(answer, docs)

    print(f"  [generate_answer] Response ({len(answer.split())} words):")
    print(f"  {answer[:200]}{'...' if len(answer) > 200 else ''}")

    scores = evaluate_run(answer, query, docs)
    print(f"\n  [evaluation]")
    print(f"    relevance:    {scores['relevance_score']:.2%}")
    print(f"    groundedness: {scores['groundedness_score']:.2%}")
    print(f"    hallucination risk: {scores['hallucination_risk']:.2%}")
    print(f"    quality:      {scores['quality_score']:.2%}")

    run_id = get_run_id()
    if run_id:
        print(f"\n  [tracechain] Run ID: {run_id}")
        print(f"  [tracechain] View at: http://localhost:3000/runs/{run_id}")

    return {
        "answer":     validated["answer"],
        "grounded":   validated["grounded"],
        "word_count": validated["word_count"],
        "evaluation": scores,
        "run_id":     run_id,
    }


# -- Entry point ---------------------------------------------------------------

DEMO_QUESTIONS = [
    "How do I reset my password?",
    "What is your refund policy?",
    "Can I use the product on multiple devices?",
    "How do I export my data?",
    "Why is my payment failing?",
]


def main():
    question = sys.argv[1] if len(sys.argv) > 1 else None

    if question:
        questions = [question]
    else:
        # run a small demo set
        questions = DEMO_QUESTIONS[:3]
        print("\nNo question provided - running 3 demo questions.")
        print("Usage: python examples/customer_support_agent.py \"Your question here\"")

    print("\n" + "="*60)
    print("  TraceChain - Customer Support Agent")
    print("="*60)

    backend_url = os.getenv("TRACECHAIN_BACKEND_URL", "http://localhost:8000")
    openai_key  = os.getenv("OPENAI_API_KEY", "")
    print(f"  Backend:    {backend_url}")
    print(f"  OpenAI key: {'set (ok)' if openai_key else 'not set - using mock responses'}")

    results = []
    for q in questions:
        try:
            result = support_agent(q)
            results.append({"question": q, "status": "success", **result})
        except Exception as e:
            print(f"\n  [ERROR] Workflow failed: {e}")
            results.append({"question": q, "status": "failed", "error": str(e)})

    print(f"\n{'='*60}")
    print(f"  Completed {len(results)} run(s)")
    print(f"  Successful: {sum(1 for r in results if r['status'] == 'success')}")
    print(f"  Failed:     {sum(1 for r in results if r['status'] == 'failed')}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
