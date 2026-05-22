# tracechain

Observability for LLM workflows. Trace runs, steps, and model calls with full support for streaming, async, retries, tool calling, and multi-turn conversations.

```python
from tracechain import workflow, step, observe_llm

@workflow(name="rag_pipeline")
def rag_pipeline(query: str) -> str:
    docs = retrieve(query)
    return generate(query, docs)

@step(name="retrieve", retries=2)
def retrieve(query: str) -> list[str]:
    return vector_db.search(query)

@step(name="generate")
def generate(query: str, docs: list[str]) -> str:
    with observe_llm("gpt_call", model="gpt-4o", prompt=query) as obs:
        resp = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[system_msg, *build_context(docs), user_msg(query)],
            tools=[citation_tool],          # tool calling — fully supported
        )
        obs.record(resp)                    # auto-extracts tokens and cost
    return resp.choices[0].message.content
```

---

## Installation

```bash
pip install tracechain                        # core only
pip install 'tracechain[openai]'              # + OpenAI client
pip install 'tracechain[anthropic]'           # + Anthropic client
pip install 'tracechain[otel]'                # + OpenTelemetry export
pip install 'tracechain[all]'                 # everything
```

**Requires Python ≥ 3.9. No mandatory dependencies beyond `httpx` and `python-dotenv`.**

---

## Zero-infrastructure quickstart (local mode)

No backend required. Data goes to a local SQLite file.

```bash
TRACECHAIN_MODE=local python my_app.py
```

```python
# Or in code:
from tracechain import TraceChainClient

client = TraceChainClient(mode="local", db_path="./traces.db")
```

Everything works identically in local mode — the schema, the decorator API, evaluations.

---

## Core concepts

### `@workflow` — the outermost boundary

Wraps a function representing one end-to-end execution. Creates a **run** record with input, output, total cost, and total tokens.

```python
from tracechain import workflow

@workflow(name="summarize")
def summarize(text: str) -> str:
    ...

# Async works identically:
@workflow(name="summarize")
async def summarize(text: str) -> str:
    ...
```

### `@step` — named, timed, retriable substeps

Each step creates a child record under the current run with exponential backoff and jitter.

```python
from tracechain import step

@step(name="fetch_docs", retries=3, retry_delay=0.5, retry_max_delay=10.0)
def fetch_docs(query: str) -> list[dict]:
    return requests.get(f"/search?q={query}").json()
```

### `observe_llm()` — watch any LLM call

The primary API for tracing model calls. You own the call; TraceChain just observes. Supports any model, any client, any parameters.

```python
from tracechain import observe_llm

with observe_llm("chat", model="gpt-4o", provider="openai", prompt=user_message) as obs:
    resp = openai_client.chat.completions.create(
        model="gpt-4o",
        messages=conversation_history,       # multi-turn
        tools=tools,                         # function calling
        response_format={"type": "json_object"},
    )
    obs.record(resp)                         # auto-extracts from ChatCompletion

# Async:
async with observe_llm("chat", model="claude-3-5-sonnet", provider="anthropic") as obs:
    resp = await async_client.messages.create(...)
    obs.record(resp)                         # auto-extracts from Anthropic Message

# Custom / local LLM — pass values manually:
with observe_llm("ollama", model="llama3", provider="ollama") as obs:
    result = ollama.generate(model="llama3", prompt=prompt)
    obs.record(
        response=result["response"],
        input_tokens=result["prompt_eval_count"],
        output_tokens=result["eval_count"],
    )
```

**Auto-extraction** supports OpenAI `ChatCompletion` and Anthropic `Message` objects via duck-typing — no hard import of either library required.

### Streaming

```python
with observe_llm("stream", model="gpt-4o", is_stream=True) as obs:
    response_text = ""
    for chunk in openai_client.chat.completions.create(..., stream=True):
        token = chunk.choices[0].delta.content or ""
        if token:
            obs.on_chunk()          # records time-to-first-token on first call
            response_text += token
    obs.record(response=response_text, input_tokens=in_t, output_tokens=out_t)
```

---

## `@llm_step` (batteries-included, simple mode)

For prototypes where you don't need the full LLM API surface. Just return a prompt string — TraceChain calls the model for you.

```python
from tracechain import llm_step

@llm_step(name="answer", model="gpt-4o-mini", provider="openai")
def answer(query: str) -> str:
    return f"Answer this question concisely: {query}"

result = answer("What is the capital of France?")
```

Supports streaming:

```python
@llm_step(name="stream_answer", model="gpt-4o-mini", stream=True)
def stream_answer(query: str) -> str:
    return f"Answer: {query}"

for token in stream_answer("What is AI?"):
    print(token, end="", flush=True)
```

> **For production use, prefer `observe_llm()`.** `@llm_step` does not support system prompts, conversation history, tool calling, or structured output.

---

## Evaluations

```python
from tracechain import workflow, evaluate_run

@workflow(name="qa_pipeline")
def qa_pipeline(question: str) -> str:
    answer = generate(question)
    evaluate_run(
        output=answer,
        reference=question,
        scores={"relevance": 0.9, "faithfulness": 0.85},
        passed=True,
    )
    return answer
```

---

## OpenTelemetry

```python
from tracechain import configure_otel

configure_otel("my-service")                     # console exporter
configure_otel("my-service", exporter="otlp")    # Jaeger / Tempo / Grafana

# Bring your own TracerProvider:
from opentelemetry.sdk.trace import TracerProvider
configure_otel("my-service", tracer_provider=my_provider)
```

Emits spans following the [OpenTelemetry GenAI semantic conventions](https://opentelemetry.io/docs/specs/semconv/gen-ai/):

| Span | Key attributes |
|------|---------------|
| `workflow.<name>` | `tracechain.workflow.name` |
| `step.<name>` | `tracechain.step.name`, `tracechain.step.type` |
| `llm.<name>` | `gen_ai.system`, `gen_ai.request.model`, `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`, `tracechain.llm.is_stream`, `tracechain.llm.ttft_ms` |

Spans are correctly nested (`workflow → step → llm`) via `context.attach/detach`.

---

## Configuration

| Environment variable | Default | Description |
|---|---|---|
| `TRACECHAIN_BACKEND_URL` | `http://localhost:8000` | Backend API URL |
| `TRACECHAIN_ENABLED` | `true` | Set `false` to disable all tracing |
| `TRACECHAIN_TIMEOUT` | `5000` | HTTP timeout in milliseconds |
| `TRACECHAIN_MODE` | `http` | `http` (backend) or `local` (SQLite) |
| `TRACECHAIN_DB_PATH` | `./tracechain.db` | SQLite file path (local mode only) |

**Silent-on-failure by design.** Backend errors never raise exceptions or crash your application.

---

## License

MIT
