# Deployment (Docker + CI/CD + Observability)

## Local run with Docker Compose

From repo root:

```bash
docker compose up --build
```

Services:
- **Frontend**: `http://localhost:4005`
- **Backend**: `http://localhost:8001`
- **MongoDB**: `mongodb://localhost:27017`

### Environment variables

You can set these via a local `.env` file next to `docker-compose.yml` (Docker Compose auto-loads it):

- `JWT_SECRET_KEY` (recommended)
- `HF_TOKEN`, `HF_MODEL`
- `DEEPSEEK_API_KEY`, `DEEPSEEK_BASE_URL`, `DEEPSEEK_MODEL`
- `SLA_CHECK_INTERVAL_SECONDS`, `SLA_DUE_SOON_HOURS`
- `MONITORING_TICK_SECONDS`

## CI/CD (GitHub Actions)

Workflow: `.github/workflows/ci.yml`

It runs:
- **Docker image builds** for `backend/` and `frontend/`
- **Backend lint** via `flake8`

## Observability

### Health endpoints
- `GET /healthz` (process up)
- `GET /readyz` (checks Mongo connectivity)

### Request logs
Backend emits one JSON log line per request with:
- method, path, status, duration_ms

