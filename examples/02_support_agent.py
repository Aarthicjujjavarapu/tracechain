"""
Example 2: Customer Support Agent
==================================
A multi-step support agent that demonstrates:
  - Multiple @llm_step calls in one workflow (intent + response)
  - @step with retries (knowledge base lookup)
  - evaluate_run with structured context
  - Running multiple queries to populate the dashboard

Run:
    cd TraceChain
    pip install -e sdk/
    python examples/02_support_agent.py

Works without OPENAI_API_KEY (uses built-in mock LLM).
Set OPENAI_API_KEY to use the real model.
"""
import logging
import sys
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s  %(name)s  %(message)s",
    stream=sys.stdout,
)

from tracechain import workflow, step, llm_step, evaluate_run

# ── Knowledge base ────────────────────────────────────────────────────────────
KNOWLEDGE_BASE: dict[str, list[str]] = {
    "billing": [
        "To update your payment method, go to Account → Billing → Payment Methods. "
        "Click 'Add Payment Method' and enter your card details. Your next invoice "
        "will be charged to the new card automatically.",

        "Invoices are generated on the 1st of each month. You can download past "
        "invoices from Account → Billing → Invoice History. Invoices are also "
        "emailed to the billing contact on file.",

        "If a payment fails, we retry after 3 days and again after 7 days. After "
        "two failed retries, your account is paused. Contact support to reactivate.",
    ],
    "technical": [
        "If you encounter a 429 rate limit error, implement exponential backoff "
        "with jitter. Our API allows 60 requests per minute on the Starter plan "
        "and 600 requests per minute on the Pro plan.",

        "Webhook events are retried up to 5 times with exponential backoff if your "
        "endpoint returns a non-2xx status. Enable webhook logs in your dashboard "
        "to debug delivery failures.",

        "API keys can be rotated in Settings → API → Manage Keys. Old keys remain "
        "valid for 24 hours after rotation to allow for a safe transition.",
    ],
    "account": [
        "To change your email address, go to Account → Profile → Contact Info. "
        "A verification link will be sent to both the old and new address. "
        "The change takes effect after both are confirmed.",

        "You can add up to 10 team members on the Starter plan. Go to "
        "Settings → Team → Invite Members. Members can be assigned Admin, "
        "Editor, or Viewer roles.",

        "To delete your account, go to Account → Danger Zone → Delete Account. "
        "This action is irreversible. All data will be permanently removed within "
        "30 days.",
    ],
    "general": [
        "Our support team is available Monday–Friday, 9am–6pm EST. "
        "You can also search our help center at help.example.com for "
        "instant answers to common questions.",
    ],
}

INTENTS = ["billing", "technical", "account", "general"]


# ── Steps ─────────────────────────────────────────────────────────────────────

@llm_step(name="classify_intent", model="gpt-4o-mini", prompt_version="intent-v1")
def classify_intent(message: str) -> str:
    """Build a classification prompt. Decorator returns the LLM's response."""
    options = ", ".join(INTENTS)
    return (
        f"Classify the following customer support message into exactly ONE of these "
        f"categories: {options}.\n\n"
        f"Respond with only the category name, nothing else.\n\n"
        f"Message: {message}"
    )


@step(name="fetch_kb_articles", retries=2)
def fetch_kb_articles(intent: str, query: str) -> list[str]:
    """Look up knowledge base articles for the classified intent."""
    # Normalise the intent — the LLM may return "Billing" or "BILLING"
    intent_clean = intent.strip().lower()
    if intent_clean not in KNOWLEDGE_BASE:
        # fall back to keyword matching
        for kb_intent in INTENTS:
            if kb_intent in query.lower() or kb_intent in intent_clean:
                intent_clean = kb_intent
                break
        else:
            intent_clean = "general"

    articles = KNOWLEDGE_BASE[intent_clean]
    print(f"  Intent: '{intent_clean}' → {len(articles)} articles")
    return articles


@llm_step(name="draft_response", model="gpt-4o-mini", prompt_version="support-response-v2")
def draft_response(customer_message: str, intent: str, articles: list[str]) -> str:
    """Build the response prompt. Decorator returns the LLM's draft."""
    kb_text = "\n\n".join(
        f"  - {article}" for article in articles
    )
    return (
        f"You are a friendly and professional customer support agent.\n"
        f"Answer the customer's question using ONLY the knowledge base articles below.\n"
        f"Be concise (2–4 sentences), empathetic, and actionable.\n\n"
        f"Knowledge Base ({intent}):\n{kb_text}\n\n"
        f"Customer message: {customer_message}\n\n"
        f"Your response:"
    )


@step(name="format_response")
def format_response(draft: str, intent: str) -> str:
    """Add a professional greeting/sign-off and normalise whitespace."""
    greeting   = "Hi there! Thanks for reaching out."
    sign_off   = "Let us know if you need anything else — we're happy to help!"
    body       = draft.strip()

    if not body.endswith((".", "!", "?")):
        body += "."

    return f"{greeting}\n\n{body}\n\n{sign_off}"


# ── Workflow ──────────────────────────────────────────────────────────────────

@workflow(name="support_agent")
def support_agent(customer_message: str) -> dict:
    print(f"\n{'='*60}")
    print(f" Support Agent")
    print(f" Message: '{customer_message[:80]}'")
    print(f"{'='*60}")

    # Step 1: classify intent
    intent   = classify_intent(customer_message)
    print(f"  Classified as: '{intent}'")

    # Step 2: fetch knowledge base articles
    articles = fetch_kb_articles(intent, query=customer_message)

    # Step 3: draft a response
    draft    = draft_response(
        customer_message=customer_message,
        intent=intent,
        articles=articles,
    )

    # Step 4: format it
    response = format_response(draft, intent=intent)

    # Step 5: evaluate quality
    scores   = evaluate_run(
        answer=response,
        question=customer_message,
        context_docs=articles,
    )

    print(f"\n  Response:\n{response}")
    print(f"\n  Quality: {scores['quality_score']:.2f}  "
          f"Relevance: {scores['relevance_score']:.2f}  "
          f"Groundedness: {scores['groundedness_score']:.2f}")

    return {
        "intent":   intent,
        "response": response,
        "scores":   scores,
    }


# ── Entry point ───────────────────────────────────────────────────────────────

SAMPLE_TICKETS = [
    "My credit card was charged twice this month. How do I get a refund?",
    "I keep getting 429 errors when calling your API. What should I do?",
    "How do I add my colleague to my account as an admin?",
    "I can't find my invoice for last month. Can you help?",
    "My webhook stopped receiving events two days ago. How do I debug this?",
]

if __name__ == "__main__":
    if len(sys.argv) > 1:
        tickets = [" ".join(sys.argv[1:])]
    else:
        tickets = SAMPLE_TICKETS

    print(f"\nRunning {len(tickets)} support ticket(s)...")
    print("This will populate your TraceChain dashboard with real traces.\n")

    for i, ticket in enumerate(tickets, 1):
        print(f"\n[{i}/{len(tickets)}]")
        try:
            result = support_agent(ticket)
        except Exception as e:
            print(f"  ERROR: {e}")

        if i < len(tickets):
            time.sleep(0.3)   # small delay so timestamps differ in the dashboard

    print(f"\n{'='*60}")
    print(" All done! Open http://localhost:3000 to see your traces.")
    print(f"{'='*60}\n")
