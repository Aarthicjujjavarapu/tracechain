# TraceChain Helm Chart

Deploys the TraceChain LLM observability platform on Kubernetes:
backend (FastAPI) + dashboard (Next.js), optional ingress, and optional HPA.

## Quick start (SQLite, no ingress)

```bash
helm install tracechain ./helm/tracechain
kubectl port-forward svc/tracechain-dashboard 3000:3000 &
kubectl port-forward svc/tracechain-backend   8000:8000 &
open http://localhost:3000
```

## Production (PostgreSQL + ingress + TLS)

```bash
helm upgrade --install tracechain ./helm/tracechain \
  -f helm/tracechain/values.prod.yaml \
  --set database.external.url="postgresql://user:pass@db-host:5432/tracechain" \
  --set ingress.dashboardHost=tracechain.example.com \
  --set ingress.backendHost=api.tracechain.example.com \
  --set secrets.openaiApiKey="$OPENAI_API_KEY"
```

## Using an existing Secret

If you manage secrets externally (e.g. Vault, ESO, SealedSecrets):

```bash
kubectl create secret generic my-tc-secrets \
  --from-literal=DATABASE_URL="postgresql://..." \
  --from-literal=OPENAI_API_KEY="sk-..."

helm install tracechain ./helm/tracechain \
  --set secrets.existingSecret=my-tc-secrets
```

## Values reference

| Key | Default | Description |
|---|---|---|
| `backend.replicaCount` | `1` | Backend pod count |
| `backend.autoscaling.enabled` | `false` | Enable HPA |
| `backend.autoscaling.maxReplicas` | `5` | HPA max replicas |
| `database.type` | `sqlite` | `sqlite` or `external` |
| `database.sqlite.persistence.size` | `2Gi` | PVC size for SQLite |
| `database.external.url` | `""` | PostgreSQL `DATABASE_URL` |
| `dashboard.apiUrl` | auto | Override backend URL seen by browser |
| `ingress.enabled` | `false` | Create Ingress resources |
| `ingress.className` | `nginx` | IngressClass name |
| `ingress.dashboardHost` | `tracechain.example.com` | Dashboard hostname |
| `ingress.backendHost` | `api.tracechain.example.com` | Backend API hostname |
| `secrets.existingSecret` | `""` | Use an existing Secret instead |
| `secrets.openaiApiKey` | `""` | Injected as `OPENAI_API_KEY` |
| `secrets.anthropicApiKey` | `""` | Injected as `ANTHROPIC_API_KEY` |

## Architecture

```
                        Ingress (optional)
                       ┌──────┬──────────┐
                       │  /   │    /     │
                    Dashboard  Backend API
                    (port 3000) (port 8000)
                         │         │
                         └────┬────┘
                            SQLite PVC
                         or external PG
```

The dashboard's `NEXT_PUBLIC_API_URL` is automatically set to the backend
ClusterIP service. Override with `dashboard.apiUrl` when the browser cannot
reach the cluster directly (e.g. when using separate ingress hostnames — set
it to the public backend URL).

## Upgrading

```bash
helm upgrade tracechain ./helm/tracechain
```

## Uninstalling

```bash
helm uninstall tracechain
# PVC is NOT deleted automatically — delete manually if needed:
kubectl delete pvc tracechain-data
```
