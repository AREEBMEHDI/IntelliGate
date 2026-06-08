# IntelliGate — Backend

This is the cloud backend for IntelliGate. It receives AI scan payloads from the edge node, resolves vehicle and face records, enforces access rules, logs every event, and pushes real-time decisions to the dashboard via WebSocket.

## Stack

- **FastAPI** — async REST API + WebSocket
- **PostgreSQL 16 + pgvector** — relational data + 512-dim ANN face search
- **Redis 7** — cache + Celery broker
- **Celery 5** — async background jobs (alerts, cleanup)
- **Docker Compose** — local dev stack

## Quick Start

```bash
cp .env.example .env
# Fill in DB_PASSWORD, JWT_SECRET, APP_SECRET_KEY in .env

docker compose up -d --build
curl http://localhost:8000/health
```

API docs (dev only): [http://localhost:8000/docs](http://localhost:8000/docs)

## Services

| Container | Port | Description |
|---|---|---|
| `intelligate_backend` | 8000 | FastAPI application |
| `intelligate_db` | 5433 (host) | PostgreSQL + pgvector |
| `intelligate_redis` | 6379 | Redis |
| `intelligate_celery` | — | Celery worker |
| `intelligate_beat` | — | Celery beat scheduler |

## Common Commands

```bash
# Follow logs
docker compose logs -f backend

# Run tests
docker exec -it intelligate_backend python -m pytest tests/ -v

# Open a DB shell
docker exec -it intelligate_db psql -U intelligate -d intelligate

# Stop all services
docker compose down

# Wipe database and start fresh
docker compose down -v && docker compose up -d --build
```

## Environment Variables

See [`.env.example`](.env.example) for the full list with descriptions.

Required values you must set:

```env
DB_PASSWORD=<strong password>
JWT_SECRET=<64-char random string>     # python -c "import secrets; print(secrets.token_hex(32))"
APP_SECRET_KEY=<64-char random string>
```

## Bootstrap (First Run)

See the [root README](../README.md#quick-start) for full step-by-step instructions including creating the superadmin, facility, gate, and test vehicle.
