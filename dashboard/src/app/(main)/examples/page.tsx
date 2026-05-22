import Card from "@/components/ui/Card";
import CodeBlock from "@/components/ui/CodeBlock";

const SNIPPETS = [
  {
    title: "Basic Workflow",
    desc: "Wrap any function as a traced workflow.",
    code: `from tracechain import workflow, step, llm_step

@workflow(name="my_pipeline")
def my_pipeline(query: str):
    docs   = retrieve(query)
    answer = generate(query, docs)
    return answer

@step(name="retrieve", retries=1)
def retrieve(query: str) -> list[str]:
    # fetch from your vector store / DB
    return ["doc1 content", "doc2 content"]

@llm_step(name="generate", model="gpt-4o-mini", prompt_version="v2")
def generate(query: str, docs: list[str]) -> str:
    return f"Answer using these docs: {query}\\n\\n{docs}"

# Run it — traces appear in dashboard automatically
result = my_pipeline("How do I reset my password?")`,
  },
  {
    title: "Step Retry Policy",
    desc: "Automatically retry flaky steps with configurable backoff.",
    code: `from tracechain import step

@step(name="call_external_api", retries=3)
def call_external_api(payload: dict) -> dict:
    """This step will retry up to 3 times on any exception."""
    import httpx
    resp = httpx.post("https://api.example.com/process", json=payload)
    resp.raise_for_status()
    return resp.json()`,
  },
  {
    title: "Evaluation",
    desc: "Score LLM outputs automatically — no evaluator LLM needed.",
    code: `from tracechain import workflow, step, llm_step, evaluate_run

@workflow(name="qa_agent")
def qa_agent(question: str) -> dict:
    docs   = search_docs(question)
    answer = generate_answer(question, docs)

    # Rule-based scoring: relevance, groundedness, hallucination risk, quality
    scores = evaluate_run(answer, question, context_docs=docs)

    print(f"Quality:      {scores['quality_score']:.0%}")
    print(f"Groundedness: {scores['groundedness_score']:.0%}")
    print(f"Hallucination risk: {scores['hallucination_risk']:.0%}")

    return {"answer": answer, "scores": scores}`,
  },
  {
    title: "Replay a Failed Run",
    desc: "Re-run any historical run from the SDK or dashboard.",
    code: `from tracechain import trigger_replay

# Replay from the SDK
new_run_id = trigger_replay("original-run-uuid-here")
print(f"Replay started: {new_run_id}")

# Or POST from curl:
# curl -X POST http://localhost:8000/runs/{run_id}/replay`,
  },
  {
    title: "Custom Client Config",
    desc: "Point the SDK at a different backend or disable tracing for tests.",
    code: `from tracechain import TraceChainConfig, TraceChainClient, workflow

# Custom backend
cfg = TraceChainConfig(
    base_url="https://tracechain.mycompany.com",
    enabled=True,
    timeout=10.0,
)
client = TraceChainClient(config=cfg)

@workflow(name="my_workflow", client=client)
def my_workflow(x: str):
    return x

# Disable for tests (no HTTP calls)
test_cfg = TraceChainConfig(enabled=False)`,
  },
  {
    title: "Prompt Versioning",
    desc: "Tag LLM calls with a prompt version for A/B comparison.",
    code: `from tracechain import llm_step

# v1 — simple instruction
@llm_step(name="answer_v1", model="gpt-4o-mini", prompt_version="v1")
def answer_v1(query: str, docs: list[str]) -> str:
    return f"Answer: {query}\\n\\nDocs: {docs}"

# v2 — more detailed instruction
@llm_step(name="answer_v2", model="gpt-4o-mini", prompt_version="v2")
def answer_v2(query: str, docs: list[str]) -> str:
    return (
        "You are a precise assistant. Answer using ONLY the docs below.\\n"
        f"Question: {query}\\nContext: {docs}\\nAnswer:"
    )

# Compare v1 vs v2 on the Prompts page in the dashboard`,
  },
];

export default function ExamplesPage() {
  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-xl font-semibold text-white">SDK Examples</h1>
        <p className="text-sm text-slate-500 mt-1">Copy-paste patterns for common TraceChain use cases</p>
      </div>

      {/* Quick-start */}
      <Card>
        <div className="flex items-start gap-4">
          <div className="w-8 h-8 rounded-lg bg-brand-500/10 border border-brand-500/20 flex items-center justify-center shrink-0 mt-0.5">
            <span className="text-brand-400 text-sm font-bold">1</span>
          </div>
          <div>
            <h2 className="text-sm font-semibold text-slate-200">Quick start</h2>
            <div className="mt-3 space-y-1 text-sm text-slate-400 font-mono bg-[#0d0f1a] rounded-lg p-4">
              <p><span className="text-slate-600"># install</span></p>
              <p>pip install -e ./sdk</p>
              <p className="mt-2"><span className="text-slate-600"># start backend + DB</span></p>
              <p>docker-compose up -d</p>
              <p className="mt-2"><span className="text-slate-600"># run example</span></p>
              <p>python examples/02_support_agent.py</p>
            </div>
          </div>
        </div>
      </Card>

      {/* Code snippets */}
      <div className="space-y-6">
        {SNIPPETS.map(({ title, desc, code }) => (
          <div key={title}>
            <h2 className="text-sm font-semibold text-slate-200 mb-1">{title}</h2>
            <p className="text-xs text-slate-500 mb-3">{desc}</p>
            <CodeBlock code={code} language="python" />
          </div>
        ))}
      </div>
    </div>
  );
}
