# TraceChain — Deployment Guide

Four production-ready deployment targets are covered below. Choose one:

| Option | Best for | Cost |
|---|---|---|
| **Kubernetes / Helm** | Production, autoscaling, GitOps | Cluster cost |
| **Railway** | Quickest end-to-end cloud deploy | ~$5–10/mo (hobby) |
| **Render** | Free tier, PostgreSQL add-on | Free (limited) or $7/mo |
| **Docker Compose (VPS)** | Full control on DigitalOcean / Hetzner | ~$6/mo |

---

## Option K — Kubernetes with Helm

The `helm/tracechain` chart deploys the backend + dashboard with configurable
persistence, ingress, and horizontal pod autoscaling.

### Prerequisites

- Kubernetes cluster (EKS, GKE, AKS, k3s, …)
- Helm 3+
- NGINX Ingress Controller (if `ingress.enabled: true`)
- cert-manager (if TLS is required)

### Quick install (SQLite, no ingress)

```bash
helm install tracechain ./helm/tracechain

kubectl port-forward svc/tracechain-dashboard 3000:3000
# open http://localhost:3000
```

### Production install (PostgreSQL + ingress + HPA)

```bash
helm upgrade --install tracechain ./helm/tracechain \
  -f helm/tracechain/values.prod.yaml \
  --set database.external.url="postgresql://user:pass@host:5432/tracechain" \
  --set ingress.dashboardHost=tracechain.example.com \
  --set ingress.backendHost=api.tracechain.example.com \
  --set secrets.openaiApiKey="$OPENAI_API_KEY"
```

See [`helm/tracechain/README.md`](helm/tracechain/README.md) for the full values reference.

---

The Next.js dashboard can be deployed separately on **Vercel** (free) regardless of which backend option you choose.

---

## Option A — Railway

Railway can deploy all three services (Postgres, backend, dashboard) from one repo.

### 1. Create a Railway project

```
railway login
railway init   # inside the TraceChain repo root
```

### 2. Add a PostgreSQL plugin

In the Railway dashboard → **New** → **Database** → **PostgreSQL**.

Copy the `DATABASE_URL` from the plugin's **Variables** tab.

### 3. Deploy the backend

```bash
cd backend
railway up --service backend
```

Set these environment variables in the Railway dashboard for the `backend` service:

```
DATABASE_URL=<from the postgres plugin>
TRACECHAIN_ENV=production
```

Railway auto-detects the `Dockerfile` in `backend/` and builds it.

### 4. Deploy the dashboard

```bash
cd dashboard
railway up --service dashboard
```

Set:

```
NEXT_PUBLIC_API_URL=https://<your-backend-railway-url>
```

Railway auto-detects Next.js and builds with `npm run build && npm start`.

### 5. Seed demo data (optional)

```bash
DATABASE_URL=<prod-url> python backend/seed.py
```

---

## Option B — Render

### 1. Create a PostgreSQL database

Render dashboard → **New** → **PostgreSQL** → copy the **External Database URL**.

### 2. Deploy the backend as a Web Service

- **New** → **Web Service** → connect your GitHub repo
- **Root directory:** `backend`
- **Runtime:** Docker
- **Dockerfile path:** `backend/Dockerfile`

Environment variables:

```
DATABASE_URL=<render postgres external url>
TRACECHAIN_ENV=production
```

Note the service URL (e.g. `https://tracechain-api.onrender.com`).

### 3. Deploy the dashboard as a Web Service

- **New** → **Web Service** → same repo
- **Root directory:** `dashboard`
- **Runtime:** Node
- **Build command:** `npm install && npm run build`
- **Start command:** `npm start`

Environment variables:

```
NEXT_PUBLIC_API_URL=https://tracechain-api.onrender.com
```

### 4. CORS

If the dashboard and backend are on different subdomains, update `backend/app/main.py`:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://your-dashboard.onrender.com"],
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## Option C — Docker Compose on a VPS

This deploys the full stack on a single server (DigitalOcean Droplet, Hetzner Cloud, etc.).

### 1. Provision a server

Any Linux server with 1 GB RAM is sufficient. Install Docker and Docker Compose:

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
```

### 2. Clone the repo

```bash
git clone https://github.com/yourname/tracechain
cd tracechain
cp .env.example .env
```

Edit `.env`:

```dotenv
POSTGRES_USER=tracechain
POSTGRES_PASSWORD=<strong-random-password>
POSTGRES_DB=tracechain
DATABASE_URL=postgresql://tracechain:<password>@postgres:5432/tracechain
TRACECHAIN_ENV=production
NEXT_PUBLIC_API_URL=http://<your-server-ip>:8000
```

### 3. Build and start

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

Services:
- Backend: `http://<ip>:8000`
- Dashboard: `http://<ip>:3000`
- Postgres: internal only

### 4. Seed demo data

```bash
docker compose exec backend python seed.py
```

### 5. Point a domain (optional)

Install nginx and configure reverse proxy:

```nginx
server {
    listen 80;
    server_name tracechain.yourdomain.com;

    location /api/ {
        proxy_pass http://localhost:8000/;
    }

    location / {
        proxy_pass http://localhost:3000;
    }
}
```

Then enable HTTPS with Certbot:

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d tracechain.yourdomain.com
```

---

## Option D — Vercel (dashboard only)

The Next.js dashboard can be deployed to Vercel independently while the backend runs anywhere.

### Steps

1. Push the repo to GitHub.
2. Go to [vercel.com](https://vercel.com) → **New Project** → import the repo.
3. Set **Root Directory** to `dashboard`.
4. Add environment variable:
   ```
   NEXT_PUBLIC_API_URL=https://your-backend-url
   ```
5. Deploy. Vercel handles build + CDN automatically.

---

## Production docker-compose

`docker-compose.prod.yml` adds the dashboard service and disables hot-reload:

```yaml
version: "3.9"

services:
  postgres:
    image: postgres:15-alpine
    container_name: tracechain_postgres
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-tracechain}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-tracechain_secret}
      POSTGRES_DB: ${POSTGRES_DB:-tracechain}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-tracechain}"]
      interval: 5s
      timeout: 5s
      retries: 5

  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: tracechain_backend
    environment:
      DATABASE_URL: ${DATABASE_URL}
      TRACECHAIN_ENV: production
    ports:
      - "8000:8000"
    depends_on:
      postgres:
        condition: service_healthy

  dashboard:
    build:
      context: ./dashboard
      dockerfile: Dockerfile
    container_name: tracechain_dashboard
    environment:
      NEXT_PUBLIC_API_URL: ${NEXT_PUBLIC_API_URL:-http://localhost:8000}
    ports:
      - "3000:3000"
    depends_on:
      - backend

volumes:
  postgres_data:
```

---

## Environment variable reference

| Variable | Required | Description |
|---|---|---|
| `DATABASE_URL` | Yes (backend) | Full PostgreSQL connection string |
| `POSTGRES_USER` | Yes (postgres service) | DB username |
| `POSTGRES_PASSWORD` | Yes (postgres service) | DB password |
| `POSTGRES_DB` | Yes (postgres service) | DB name |
| `TRACECHAIN_ENV` | No | `development` or `production` |
| `NEXT_PUBLIC_API_URL` | Yes (dashboard) | Full URL of the backend API |
| `TRACECHAIN_BACKEND_URL` | No (SDK) | Where the Python SDK sends traces |
| `TRACECHAIN_ENABLED` | No (SDK) | Set `false` to disable tracing (e.g. CI) |
| `OPENAI_API_KEY` | No | Required only for real LLM calls |

---

## Health checks

Once deployed:

```bash
# Backend health
curl https://your-backend/health
# {"status":"ok","version":"0.1.0"}

# Swagger UI
open https://your-backend/docs

# Dashboard
open https://your-dashboard
```
