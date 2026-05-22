---
id: installation
title: Installation
sidebar_position: 1
---

# Installation

TraceChain has three components. You need all three for a complete setup, but you can instrument your code with the SDK before the backend is running.

## Prerequisites

| Tool | Minimum version |
|---|---|
| Python | 3.10+ |
| Node.js | 18+ |
| Docker + Docker Compose | any recent version |
| PostgreSQL | 15+ (or use Docker) |

---

## 1. Clone the repository

```bash
git clone https://github.com/Aarthicjujjavarapu/tracechain.git
cd tracechain
```

---

## 2. Install the Python SDK

Install from the local `sdk/` directory (editable mode for development):

```bash
pip install -e sdk/
```

Or install dependencies directly:

```bash
pip install -r sdk/requirements.txt
```

The SDK depends on:

| Package | Purpose |
|---|---|
| `httpx` | Non-blocking HTTP to the backend |
| `pydantic` | Schema validation |
| `python-dotenv` | `.env` loading |
| `openai` | Used in example workflows |

---

## 3. Start the backend

### Option A — Docker Compose (recommended)

```bash
docker compose up -d
```

This starts:
- `tracechain-db` — PostgreSQL 15 on port `5432`
- `tracechain-api` — FastAPI on port `8000`

Migrations run automatically on first start.

### Option B — local Python

```bash
# 1. Create and activate a virtualenv
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 2. Install backend deps
pip install -r backend/requirements.txt

# 3. Point at a running Postgres
export DATABASE_URL="postgresql://tracechain:tracechain@localhost:5432/tracechain"

# 4. Run migrations
cd backend && alembic upgrade head && cd ..

# 5. Start the API
uvicorn backend.app.main:app --reload --port 8000
```

---

## 4. Install the dashboard

```bash
cd dashboard
npm install
npm run dev     # http://localhost:3000
```

For production:

```bash
npm run build
npm start
```

---

## 5. Verify

```bash
curl http://localhost:8000/health
# {"status":"ok","db":"connected"}
```

Open the dashboard at [http://localhost:3000](http://localhost:3000).

---

## Next steps

- [5-minute quickstart →](quickstart)
- [Configuration reference →](configuration)
