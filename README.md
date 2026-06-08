# IntelliGate

[![CI](https://github.com/AREEBMEHDI/IntelliGate/actions/workflows/ci.yml/badge.svg)](https://github.com/AREEBMEHDI/IntelliGate/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql&logoColor=white)](https://postgresql.org)
[![Redis](https://img.shields.io/badge/Redis-7-DC382D?logo=redis&logoColor=white)](https://redis.io)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)](https://docker.com)
[![YOLOv8](https://img.shields.io/badge/YOLOv8-Ultralytics-FF6B6B)](https://ultralytics.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**IntelliGate** is an end-to-end AI-powered gate security system that performs real-time **vehicle detection**, **license plate OCR**, and **face recognition** at facility entry points, with a cloud backend that enforces access rules and streams decisions live to a security dashboard.

---

## Table of Contents

- [System Architecture](#system-architecture)
- [Key Features](#key-features)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Quick Start](#quick-start)
- [Backend Setup](#backend-setup)
- [AI Engine Setup](#ai-engine-setup)
- [API Reference](#api-reference)
- [Database Schema](#database-schema)
- [Configuration Reference](#configuration-reference)
- [Running Tests](#running-tests)
- [Deployment Notes](#deployment-notes)
- [Roadmap](#roadmap)

---

## System Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                         EDGE NODE (AI Engine)                    │
│                                                                  │
│  Camera → YOLOv8 → Vehicle Detection                            │
│                 → PaddleOCR → Plate Number (text)               │
│                 → InsightFace → Face Embedding (512-dim)         │
│                                          │                       │
│  MJPEG Stream → Dashboard  (port 5001)  │                       │
└─────────────────────────────────────────┼───────────────────────┘
                                          │  POST /api/scan/
                                          │  X-API-Key: <facility_key>
                                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                    CLOUD BACKEND (FastAPI)                       │
│                                                                  │
│  Auth Service ─── JWT + bcrypt                                  │
│  Decision Engine ─ plate lookup + face cosine similarity        │
│  WebSocket Hub ─── real-time push to dashboard                  │
│  Celery Workers ── async alerts (SMS/email) + media cleanup      │
│                                          │                       │
│  PostgreSQL + pgvector  ◄───────────────┘                       │
│  Redis (cache + queue)                                          │
│  Cloudflare R2 (media storage)                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Flow:**
1. AI engine captures a frame every 15 ticks, runs all three detectors in parallel.
2. Results (plate text + face embeddings) are POST-ed to the cloud backend with an API key.
3. Backend resolves the vehicle against the approved list and the driver against stored face embeddings using ANN cosine search.
4. Decision (`allowed` / `denied` / `allowed_with_alert`) is returned in < 5 s and pushed via WebSocket to any connected dashboard.
5. All events are immutably logged in `entry_logs` with full metadata.

---

## Key Features

| Feature | Detail |
|---|---|
| **Vehicle Detection** | YOLOv8-nano — cars, motorcycles, buses, trucks |
| **Plate OCR** | PaddleOCR with Otsu binarisation pre-processing |
| **Face Recognition** | InsightFace ArcFace — 512-dim embeddings, IVFFlat cosine ANN |
| **Access Decisions** | `allowed`, `denied`, `allowed_with_alert` with reasons |
| **Real-time Dashboard** | WebSocket push on every scan result |
| **MJPEG Stream** | Live annotated video feed from edge node |
| **Role-Based Auth** | `guard`, `admin`, `superadmin` via JWT |
| **Multi-Facility** | One backend, multiple physical sites each with isolated data |
| **Async Background Jobs** | Celery + Redis for SMS/email alerts and media cleanup |
| **Offline Edge Sync** | `edge_sync_queue` table — logs survive network drops |
| **Immutable Audit Log** | `entry_logs` — full history, never deleted |
| **Row-Level Security** | PostgreSQL RLS — guards only see their own facility |

---

## Tech Stack

### Backend
| Layer | Technology |
|---|---|
| API Framework | FastAPI 0.111 + Uvicorn |
| ORM | SQLAlchemy 2.0 (async) |
| Database | PostgreSQL 16 + pgvector |
| Cache / Queue | Redis 7 + Celery 5 |
| Auth | python-jose (JWT) + passlib/bcrypt |
| Storage | Cloudflare R2 (boto3 S3-compatible) |
| Notifications | Twilio SMS + SendGrid email |
| Monitoring | Sentry SDK |
| Validation | Pydantic v2 + pydantic-settings |

### AI Engine
| Component | Technology |
|---|---|
| Vehicle Detection | YOLOv8-nano (Ultralytics) |
| Plate OCR | PaddleOCR 2.7 |
| Face Recognition | InsightFace 0.7 (ArcFace, buffalo_sc) |
| Inference Runtime | ONNX Runtime (CPU / Apple MPS) |
| HTTP Client | httpx (async) |
| Video Streaming | Flask MJPEG server |

---

## Project Structure

```
intelligate/
├── README.md
├── LICENSE
├── CONTRIBUTING.md
├── SECURITY.md
├── .gitignore
│
├── smart-access-full/              # Cloud backend
│   ├── docker-compose.yml          # Postgres, Redis, FastAPI, Celery
│   ├── .env.example                # Environment variable template
│   └── backend/
│       ├── main.py                 # FastAPI app + lifespan
│       ├── Dockerfile
│       ├── requirements.txt
│       ├── core/
│       │   ├── config.py           # pydantic-settings config
│       │   └── database.py         # async SQLAlchemy engine
│       ├── models/
│       │   └── models.py           # ORM models (Facility, Gate, Vehicle, Employee, Visitor, EntryLog, User)
│       ├── api/routes/
│       │   ├── auth.py             # POST /api/auth/login
│       │   ├── facilities.py       # CRUD + API key rotation
│       │   ├── vehicles.py         # vehicle allowlist management
│       │   ├── employees.py        # employee + face enrollment
│       │   ├── visitors.py         # visitor pre-approval
│       │   ├── logs.py             # entry log query + export
│       │   ├── scan.py             # POST /api/scan/ (edge node endpoint)
│       │   └── ws.py               # WS /ws/facility/{id}
│       ├── services/
│       │   ├── decision.py         # access decision engine
│       │   ├── storage.py          # R2 file upload
│       │   ├── alerts.py           # SMS / email alert dispatch
│       │   └── websocket_manager.py
│       ├── tasks/
│       │   ├── celery_app.py
│       │   └── tasks.py            # async background jobs
│       ├── migrations/
│       │   └── init.sql            # full schema with indexes + triggers
│       └── tests/
│           └── test_decision.py
│
└── Ai engine/                      # Edge AI pipeline
    ├── live_pipeline.py            # main camera loop + MJPEG stream
    ├── send_to_backend.py          # smoke test — sends fake scans
    ├── test_pipeline.py            # camera test without backend
    ├── test_image.py               # static image test
    ├── install.sh                  # one-shot venv + deps setup
    ├── requirements.txt
    └── config.env.example          # AI engine config template
```

---

## Quick Start

### Prerequisites

- Docker Desktop
- Python 3.11+ (for AI engine)
- A webcam (for the live pipeline)
- macOS, Linux, or WSL2

### 1. Clone and configure

```bash
git clone https://github.com/your-username/intelligate.git
cd intelligate

# Backend
cp smart-access-full/.env.example smart-access-full/.env
# Edit smart-access-full/.env — set DB_PASSWORD, JWT_SECRET, APP_SECRET_KEY

# AI engine
cp "Ai engine/config.env.example" "Ai engine/config.env"
# Edit Ai engine/config.env after completing backend setup below
```

### 2. Start the backend

```bash
cd smart-access-full
docker compose up -d --build
curl http://localhost:8000/health   # → {"status":"ok","env":"development"}
```

Open the interactive API docs: [http://localhost:8000/docs](http://localhost:8000/docs)

### 3. Bootstrap data

```bash
# Create superadmin
docker exec -it intelligate_backend python -c "
import asyncio, uuid
from core.database import AsyncSessionLocal
from models.models import User
from passlib.context import CryptContext

async def main():
    pwd = CryptContext(schemes=['bcrypt']).hash('change_me')
    async with AsyncSessionLocal() as db:
        db.add(User(id=uuid.uuid4(), name='Super Admin',
                    email='admin@example.com', password_hash=pwd, role='superadmin'))
        await db.commit()
        print('admin@example.com created')
asyncio.run(main())"

# Login and save token
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login \
  -d "username=admin@example.com&password=change_me" | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# Create a facility — save the returned api_key and id
curl -s -X POST http://localhost:8000/api/facilities/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"Main Office","city":"Karachi","country":"Pakistan","timezone":"Asia/Karachi"}'
```

Copy the `api_key` and `id` from the response into `Ai engine/config.env`.

### 4. Start the AI engine

```bash
cd "Ai engine"
bash install.sh          # first time only
source venv/bin/activate
python3 live_pipeline.py
```

The pipeline opens your camera, detects vehicles and faces, and posts results to the backend. Live annotated video streams at `http://localhost:5001/video_feed`.

---

## Backend Setup

### Environment variables

Copy `.env.example` → `.env` and set all required values:

```bash
cd smart-access-full
cp .env.example .env
```

Generate secure secrets:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

Minimum required values:

```env
DB_PASSWORD=<strong password>
JWT_SECRET=<64-char random string>
APP_SECRET_KEY=<64-char random string>
DATABASE_URL=postgresql+asyncpg://intelligate:<DB_PASSWORD>@postgres:5432/intelligate
```

### Docker Compose services

| Service | Container | Port |
|---|---|---|
| FastAPI | `intelligate_backend` | 8000 |
| PostgreSQL | `intelligate_db` | 5433 (host) |
| Redis | `intelligate_redis` | 6379 |
| Celery Worker | `intelligate_celery` | — |
| Celery Beat | `intelligate_beat` | — |

```bash
# Start all services
docker compose up -d --build

# Follow backend logs
docker compose logs -f backend

# Run tests inside container
docker exec -it intelligate_backend python -m pytest tests/ -v

# Stop and remove volumes (fresh DB)
docker compose down -v
```

---

## AI Engine Setup

### Install

```bash
cd "Ai engine"
bash install.sh
```

Or manually:

```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

> **macOS camera permission:** System Settings → Privacy & Security → Camera → enable Terminal

### Configure

```bash
cp config.env.example config.env
```

Fill in `FACILITY_API_KEY` and `GATE_ID` from the backend setup step.

### Run modes

| Command | What it does |
|---|---|
| `python3 live_pipeline.py` | Full pipeline — camera + backend + MJPEG stream |
| `python3 test_pipeline.py` | Camera only — no backend needed |
| `python3 test_image.py <path>` | Static image — annotates and saves result |
| `python3 send_to_backend.py` | Smoke test — sends fake scans, no camera needed |

**Keyboard controls (live pipeline):**

| Key | Action |
|---|---|
| `Q` | Quit |
| `S` | Save screenshot to `captures/` |
| `F` | Toggle face detection |
| `P` | Toggle plate OCR |

---

## API Reference

Full interactive docs available at `/docs` when `APP_ENV=development`.

### Authentication

```
POST /api/auth/login
Content-Type: application/x-www-form-urlencoded
Body: username=<email>&password=<password>

→ { "access_token": "...", "token_type": "bearer" }
```

All protected endpoints require `Authorization: Bearer <token>`.

### Key Endpoints

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/health` | — | Service health check |
| `POST` | `/api/auth/login` | — | Login, get JWT |
| `GET` | `/api/facilities/` | JWT | List facilities |
| `POST` | `/api/facilities/` | JWT (superadmin) | Create facility, returns `api_key` |
| `POST` | `/api/facilities/{id}/rotate-key` | JWT (admin) | Rotate edge API key |
| `GET` | `/api/vehicles/` | JWT | List facility vehicles |
| `POST` | `/api/vehicles/` | JWT | Add vehicle to allowlist |
| `GET` | `/api/employees/` | JWT | List employees |
| `POST` | `/api/employees/{id}/enroll-face` | JWT | Upload face photo, store embedding |
| `GET` | `/api/visitors/` | JWT | List visitors |
| `GET` | `/api/logs/` | JWT | Query entry logs |
| `POST` | `/api/scan/` | API Key | Edge node scan submission |
| `WS` | `/ws/facility/{id}` | JWT | Real-time scan results |

### Edge Scan Payload (`POST /api/scan/`)

```json
{
  "gate_id": "uuid",
  "plate_number": "ABC123",
  "plate_confidence": 0.91,
  "persons": [
    {
      "face_embedding": [0.12, -0.34, ...],
      "face_confidence": 0.87
    }
  ],
  "edge_timestamp": "2024-01-15T10:30:00"
}
```

### Scan Response

```json
{
  "decision": "allowed",
  "decision_reason": "Approved vehicle, identified driver",
  "driver_name": "John Doe",
  "vehicle_status": "approved",
  "log_id": "uuid"
}
```

---

## Database Schema

Eight tables, all in PostgreSQL with pgvector extension:

```
facilities     ─── id, name, city, api_key (hashed), is_active
gates          ─── id, facility_id, name, gate_type (entry|exit|both)
vehicles       ─── id, facility_id, plate_number, status (approved|blacklisted|suspended)
employees      ─── id, facility_id, name, face_embedding vector(512), access_level
visitors       ─── id, facility_id, name, pre_approved, approved_until, face_embedding vector(512)
entry_logs     ─── id, gate_id, plate_number, decision, driver_name, entry_time  [immutable]
edge_sync_queue─── id, facility_id, payload JSONB, synced  [offline buffer]
users          ─── id, facility_id, email, role (guard|admin|superadmin)
```

**Notable design decisions:**
- `entry_logs` has no DELETE — full audit trail forever.
- Face embeddings use `IVFFlat` cosine ANN index for sub-millisecond search across large employee sets.
- Row-Level Security is enabled on all facility-scoped tables.
- `updated_at` auto-update triggers on `vehicles`, `employees`, `facilities`.

---

## Configuration Reference

### Backend (`smart-access-full/.env`)

| Variable | Required | Description |
|---|---|---|
| `DATABASE_URL` | Yes | PostgreSQL async DSN |
| `REDIS_URL` | Yes | Redis DSN |
| `JWT_SECRET` | Yes | Min 32-char secret for JWT signing |
| `APP_SECRET_KEY` | Yes | App-level secret key |
| `APP_ENV` | No | `development` or `production` |
| `CORS_ORIGINS` | No | Comma-separated allowed origins |
| `R2_ACCOUNT_ID` | No | Cloudflare R2 for media storage |
| `TWILIO_ACCOUNT_SID` | No | SMS alerts |
| `SENDGRID_API_KEY` | No | Email alerts |
| `SENTRY_DSN` | No | Error tracking |

### AI Engine (`Ai engine/config.env`)

| Variable | Required | Description |
|---|---|---|
| `FACILITY_API_KEY` | Yes | Returned by `POST /api/facilities/` |
| `GATE_ID` | Yes | UUID of the gate in the DB |
| `CLOUD_API_URL` | No | Backend URL (default: `http://localhost:8000`) |
| `STREAM_PORT` | No | MJPEG stream port (default: `5001`) |

---

## Running Tests

```bash
# Inside Docker
docker exec -it intelligate_backend python -m pytest tests/ -v

# Or locally (requires a running DB)
cd smart-access-full/backend
pip install pytest pytest-asyncio
pytest tests/ -v
```

Test coverage includes the decision engine logic — the most critical business-logic component.

---

## Deployment Notes

- **Never expose `/docs`** in production — set `APP_ENV=production` to disable Swagger UI.
- **Rotate API keys** after initial setup: `POST /api/facilities/{id}/rotate-key`
- **CORS** — restrict `CORS_ORIGINS` to your actual frontend domain.
- **Database** — use strong `DB_PASSWORD` and restrict the Postgres port (do not expose 5433 publicly).
- **Model files** (`.pt`) are excluded from the repo due to size — download via `ultralytics` on first run or mount them as a Docker volume.
- **Face embeddings** (`my_face_embedding.json`, `captures/`) are excluded from the repo — biometric data must never be committed.

---

## Roadmap

- [ ] Alembic migrations (replace manual `init.sql`)
- [ ] Frontend dashboard (React + WebSocket)
- [ ] RTSP camera support (replace webcam with IP cameras)
- [ ] Edge-side SQLite buffer for full offline operation
- [ ] Multi-gate fan-out WebSocket broadcasts
- [ ] Kubernetes Helm chart for production deployment
- [ ] Prometheus + Grafana metrics

---

## License

MIT — see [LICENSE](LICENSE).
