# @tracechain/sdk

**TypeScript/JavaScript SDK for TraceChain — reliability and observability for AI workflows.**

[![npm](https://img.shields.io/npm/v/@tracechain/sdk)](https://www.npmjs.com/package/@tracechain/sdk)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://github.com/Aarthicjujjavarapu/tracechain/blob/main/LICENSE)

```bash
npm install @tracechain/sdk
```

> For the Python SDK: `pip install tracechain`  
> GitHub: [github.com/Aarthicjujjavarapu/tracechain](https://github.com/Aarthicjujjavarapu/tracechain)

---

## Quick start

```typescript
import { workflow, step, observeLlm } from "@tracechain/sdk";

const pipeline = workflow("rag_pipeline", async (query: string) => {
  const docs = await retrieve(query);
  return generate(query, docs);
});

const retrieve = step("retrieve", async (query: string) => {
  return vectorDb.search(query);
}, { retries: 2 });
```

## Configuration

```typescript
import { TraceChainClient } from "@tracechain/sdk";

const client = new TraceChainClient({
  baseUrl: "http://localhost:8000",
  enabled: true,
  timeout: 5000,
});
```

Environment variables:
- `TRACECHAIN_BACKEND_URL` — backend URL (default: `http://localhost:8000`)
- `TRACECHAIN_ENABLED` — set `false` to disable tracing (default: `true`)

## OpenTelemetry

```typescript
import { configureOtel } from "@tracechain/sdk";

configureOtel({ serviceName: "my-service", exporter: "otlp" });
```

## Links

- [Full documentation](https://github.com/Aarthicjujjavarapu/tracechain)
- [Python SDK on PyPI](https://pypi.org/project/tracechain/)
- [GitHub](https://github.com/Aarthicjujjavarapu/tracechain)
- [Issues](https://github.com/Aarthicjujjavarapu/tracechain/issues)

## License

MIT
