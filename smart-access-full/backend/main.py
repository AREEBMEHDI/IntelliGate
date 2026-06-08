import sentry_sdk
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from core.config import settings
from core.database import engine, Base
from api.routes import auth, facilities, vehicles, employees, visitors, logs, scan, ws


if settings.sentry_dsn and settings.sentry_dsn.startswith(("http://", "https://")):
    sentry_sdk.init(dsn=settings.sentry_dsn, traces_sample_rate=0.2)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    # shutdown
    await engine.dispose()


app = FastAPI(
    title="IntelliGate API",
    version="1.0.0",
    docs_url="/docs" if settings.app_env == "development" else None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Routers ─────────────────────────────────
app.include_router(auth.router,        prefix="/api/auth",       tags=["auth"])
app.include_router(facilities.router,  prefix="/api/facilities", tags=["facilities"])
app.include_router(vehicles.router,    prefix="/api/vehicles",   tags=["vehicles"])
app.include_router(employees.router,   prefix="/api/employees",  tags=["employees"])
app.include_router(visitors.router,    prefix="/api/visitors",   tags=["visitors"])
app.include_router(logs.router,        prefix="/api/logs",       tags=["logs"])
app.include_router(scan.router,        prefix="/api/scan",       tags=["scan"])
app.include_router(ws.router,          prefix="/ws",             tags=["websocket"])


@app.get("/health")
async def health():
    return {"status": "ok", "env": settings.app_env}
