# Contributing to TraceChain

Thanks for your interest. TraceChain is reliability infrastructure for AI workflows — contributions that make it more correct, faster, or better integrated are always welcome.

## Before you start

- Open an issue first for anything beyond a small bug fix. This saves both of us from wasted work if the direction doesn't fit.
- Check the [ROADMAP](ROADMAP.md) to see what's already planned.

## Development setup

```bash
# Python SDK
cd sdk
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest

# TypeScript SDK
cd sdk-js
npm install
npm test
npm run typecheck

# Backend
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload

# Dashboard
cd dashboard
npm install
npm run dev
```

## Contribution types

### Bug fixes
- Reproduce the bug with a failing test first.
- Fix the bug.
- Confirm the test passes.
- Open a PR.

### New features
- Open an issue describing the problem you're solving and your proposed approach.
- Wait for maintainer feedback before writing code.
- Implementation PR should include tests and, if the feature is user-facing, an example.

### Integrations (LangChain, LlamaIndex, etc.)
- Add the integration in `sdk/tracechain/integrations/<name>.py`.
- The integration must be optional — no new mandatory dependencies.
- Add a working example in `examples/<name>/`.
- Test with `pytest.importorskip`.

### Documentation
- Docs live in `docs/`.
- Keep examples runnable — broken examples erode trust faster than missing docs.

## Code standards

**Python**
- Type annotations on all public functions.
- No comments explaining *what* the code does — only *why* if non-obvious.
- Tests in `tests/test_<module>.py`.
- `ruff` for linting, `black` for formatting (both run in CI).

**TypeScript**
- Strict mode enabled.
- No `any` on public API surfaces.
- Vitest for tests.

**Both**
- Public APIs must be backward-compatible within a minor version.
- If you're changing an event schema, update both the SDK and the backend.

## Pull request checklist

- [ ] Tests added for new behavior
- [ ] Existing tests still pass
- [ ] No new mandatory dependencies added without discussion
- [ ] CHANGELOG entry added (if user-facing)
- [ ] PR description explains *why*, not just *what*

## Commit messages

```
type: short description (≤ 72 chars)

Optional longer explanation of why, not what.
```

Types: `feat`, `fix`, `perf`, `refactor`, `test`, `docs`, `chore`

## Reporting security issues

Do not open a public issue. See [SECURITY.md](SECURITY.md).
