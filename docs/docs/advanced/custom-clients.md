---
id: custom-clients
title: Custom Clients
sidebar_position: 1
---

# Custom Clients

By default, every TraceChain decorator uses a singleton client configured from environment variables. You can override this with a custom `TraceChainClient` for more control.

## When to use a custom client

- Testing — point at a test backend or mock server
- Multi-tenancy — different workflows write to different backends
- Non-default timeout or URL without changing environment variables
- Dependency injection in a framework like FastAPI

## Creating a custom client

```python
from tracechain import TraceChainConfig, TraceChainClient

config = TraceChainConfig(
    base_url="https://staging-backend.internal:8000",
    enabled=True,
    timeout=3.0,
)
client = TraceChainClient(config)
```

## Passing a client to decorators

All decorators accept an optional `client` parameter:

```python
from tracechain import workflow, step, llm_step

@workflow(name="pipeline", client=client)
def pipeline(query: str):
    docs = retrieve(query)
    return generate(query, docs)

@step(name="retrieve", client=client)
def retrieve(query: str) -> list[str]:
    ...

@llm_step(name="generate", model="gpt-4o-mini", client=client)
def generate(query: str, docs: list[str]) -> str:
    ...
```

## Disabling tracing in tests

Use `TraceChainConfig(enabled=False)` to produce a no-op client. All decorator calls return immediately without making HTTP requests:

```python
import pytest
from tracechain import TraceChainConfig, TraceChainClient

@pytest.fixture(autouse=True)
def disable_tracing():
    config = TraceChainConfig(enabled=False)
    client = TraceChainClient(config)
    # patch the default client used by decorators
    import tracechain.client as tc_module
    original = tc_module._default_client
    tc_module._default_client = client
    yield
    tc_module._default_client = original
```

Or set `TRACECHAIN_ENABLED=false` in your test environment.

## Pointing at a test server

For integration tests that need a real backend:

```python
import pytest
import httpx
from tracechain import TraceChainConfig, TraceChainClient

TEST_BACKEND = "http://localhost:8001"

@pytest.fixture(scope="session")
def test_client():
    return TraceChainClient(TraceChainConfig(base_url=TEST_BACKEND))

def test_pipeline_creates_run(test_client):
    @workflow(name="test_pipeline", client=test_client)
    def pipeline():
        return "ok"

    pipeline()

    # verify via the API
    resp = httpx.get(f"{TEST_BACKEND}/runs?workflow_name=test_pipeline")
    assert resp.json()["total"] >= 1
```

## `TraceChainConfig` reference

```python
@dataclass
class TraceChainConfig:
    base_url: str = "http://localhost:8000"
    enabled: bool = True
    timeout: float = 5.0
```

All fields have defaults and can be overridden per-instance. The constructor reads environment variables as defaults, so you can still override selectively:

```python
# Uses env vars as base, overrides just the timeout
config = TraceChainConfig(timeout=2.0)
```
