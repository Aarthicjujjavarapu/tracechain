---
id: docker
title: Docker Deployment
sidebar_position: 1
---

# Docker Deployment

TraceChain ships a `docker-compose.yml` that starts the entire stack with one command.

## Services

| Service | Image | Port | Description |
|---|---|---|---|
| `tracechain-db` | `postgres:15-alpine` | `5432` | PostgreSQL database |
| `tracechain-api` | built from `backend/Dockerfile` | `8000` | FastAPI backend |

The dashboard is a separate Node.js process and is not in the Compose file — deploy it separately (see below).

## Quick start

```bash
# Copy and fill in environment variables
cp .env.example .env

# Start Postgres + API
docker compose up -d

# Follow logs
docker compose logs -f tracechain-api
```

## The `docker-compose.yml`

```yaml
version: "3.9"

services:
  db:
    image: postgres:15-alpine
    container_name: tracechain-db
    environment:
      POSTGRES_USER: tracechain
      POSTGRES_PASSWORD: tracechain
      POSTGRES_DB: tracechain
    ports:
      - "5432:5432"
    volumes:
      - tracechain_pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U tracechain"]
      interval: 5s
      timeout: 5s
      retries: 10

  api:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: tracechain-api
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: postgresql://tracechain:tracechain@db:5432/tracechain
    depends_on:
      db:
        condition: service_healthy

volumes:
  tracechain_pgdata:
```

## Backend Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Migrations run automatically on startup (see `app/main.py` lifespan).

## Deploying the dashboard

### Vercel (recommended)

```bash
cd dashboard
npx vercel --prod
```

Set the environment variable in Vercel:

```
NEXT_PUBLIC_API_URL=https://your-backend.example.com
```

### Docker (manual)

```dockerfile
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
ENV NEXT_PUBLIC_API_URL=https://your-backend.example.com
RUN npm run build

FROM node:20-alpine
WORKDIR /app
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public
EXPOSE 3000
CMD ["node", "server.js"]
```

Add `output: "standalone"` to `next.config.js` to enable the standalone build.

## Production checklist

- [ ] Set `DATABASE_URL` to a production PostgreSQL instance (not Docker)
- [ ] Set `ALLOWED_ORIGINS` on the backend to your dashboard domain
- [ ] Set `NEXT_PUBLIC_API_URL` on the dashboard to your backend URL
- [ ] Use a secrets manager for the database password — do not commit `.env`
- [ ] Enable SSL on the database connection
- [ ] Set up automated PostgreSQL backups
- [ ] Put the backend behind a reverse proxy (nginx, Caddy, or a cloud load balancer) with TLS

## Useful commands

```bash
# Stop all services
docker compose down

# Stop and destroy volumes (wipes all data)
docker compose down -v

# Rebuild the API image
docker compose build api

# Open a psql shell
docker compose exec db psql -U tracechain tracechain

# Run Alembic migrations manually
docker compose exec api alembic upgrade head
```
