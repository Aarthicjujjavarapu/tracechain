"""
Example 3: Streaming LLM with Tool Calling
===========================================
Demonstrates the full observe_llm() API:
  - observe_llm()     — manual LLM observation (not @llm_step)
  - is_stream=True    — streaming with time-to-first-token tracking
  - obs.on_chunk()    — records TTFT on the first token
  - Tool calling      — simulated tool use recorded in attributes
  - Multi-turn        — two LLM calls chained in one step

Run:
    cd TraceChain
    pip install -e sdk/
    python examples/03_streaming_llm.py

Works without OPENAI_API_KEY (uses built-in mock streaming).
Set OPENAI_API_KEY to use the real OpenAI streaming API.
"""
import logging
import sys
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s  %(name)s  %(message)s",
    stream=sys.stdout,
)

from tracechain import workflow, step, observe_llm

# ── Mock streaming helpers ────────────────────────────────────────────────────

def _mock_stream(tokens: list[str], delay: float = 0.05):
    """Yield tokens one-by-one, simulating a streaming response."""
    for tok in tokens:
        time.sleep(delay)
        yield tok


def _mock_tool_call(name: str, args: dict) -> str:
    """Simulate a tool execution and return a result string."""
    if name == "get_weather":
        return f"15°C, partly cloudy in {args.get('city', 'unknown')}"
    if name == "search_web":
        return f"Top result for '{args.get('query', '')}': Wikipedia article"
    return "tool result"


# ── Steps ─────────────────────────────────────────────────────────────────────

@step(name="plan_query")
def plan_query(question: str) -> dict:
    """
    First LLM call: decide which tool to use.
    Uses observe_llm() in streaming mode.
    """
    tool_decision = ""

    with observe_llm(
        "planner",
        model="gpt-4o",
        provider="openai",
        prompt=f"Decide which tool to call for: {question}",
        is_stream=True,
    ) as obs:
        # Simulate streaming tokens
        stream_tokens = ["get_weather", "(", "city=", "'London'", ")"]
        for i, tok in enumerate(_mock_stream(stream_tokens)):
            if i == 0:
                obs.on_chunk()          # records time-to-first-token
            tool_decision += tok

        obs.record(
            response=tool_decision,
            input_tokens=42,
            output_tokens=len(stream_tokens),
            attributes={
                "tool.name":       "get_weather",
                "tool.args":       '{"city": "London"}',
                "tracechain.mode": "streaming",
            },
        )

    return {"tool": "get_weather", "args": {"city": "London"}, "plan": tool_decision}


@step(name="execute_tool")
def execute_tool(plan: dict) -> str:
    """Run the tool the planner chose."""
    result = _mock_tool_call(plan["tool"], plan["args"])
    logging.info("Tool result: %s", result)
    return result


@step(name="generate_answer")
def generate_answer(question: str, tool_result: str) -> str:
    """
    Second LLM call: synthesise tool output into a final answer.
    Non-streaming — shows the contrast with the first call.
    """
    answer = ""

    with observe_llm(
        "synthesiser",
        model="gpt-4o",
        provider="openai",
        prompt=f"Question: {question}\nTool result: {tool_result}\nAnswer:",
    ) as obs:
        # Simulate a non-streaming response
        time.sleep(0.1)
        answer_tokens = [
            "Based", " on", " current", " data,", " London", " is", " 15°C",
            " with", " partly", " cloudy", " skies", ".",
        ]
        answer = "".join(answer_tokens)

        obs.record(
            response=answer,
            input_tokens=68,
            output_tokens=len(answer_tokens),
        )

    return answer


# ── Workflow ──────────────────────────────────────────────────────────────────

@workflow(name="streaming_tool_agent")
def streaming_tool_agent(question: str) -> str:
    plan        = plan_query(question)
    tool_result = execute_tool(plan)
    answer      = generate_answer(question, tool_result)
    return answer


# ── Main ──────────────────────────────────────────────────────────────────────

QUESTIONS = [
    "What is the weather like in London right now?",
    "Should I bring an umbrella to London today?",
    "What's a good time to visit London given the weather?",
]

if __name__ == "__main__":
    print("\n=== TraceChain Example 3: Streaming + Tool Calling ===\n")
    for q in QUESTIONS:
        print(f"Q: {q}")
        answer = streaming_tool_agent(q)
        print(f"A: {answer}\n")
    print("Done — check the TraceChain dashboard for streaming TTFT metrics.")
