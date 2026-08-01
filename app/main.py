"""FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.database import create_db_client, reset_beanie_state
from app.routes.questions import router as questions_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create the Mongo client on startup and close it on shutdown.

    Beanie initialization is deferred until a request actually touches the
    database so the process can boot even when MongoDB is temporarily offline.
    """

    app.state.mongo_client = create_db_client()
    yield
    app.state.mongo_client.close()
    reset_beanie_state()


settings = get_settings()
app = FastAPI(title=settings.app_name, version="1.0.0", lifespan=lifespan)

allow_origins = [origin.strip() for origin in settings.cors_allow_origins.split(",") if origin.strip()]
if allow_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if allow_origins == ["*"] else allow_origins,
        allow_credentials=settings.cors_allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(questions_router)


@app.get("/")
async def root() -> dict[str, str]:
    """Simple health-style root endpoint for container checks."""

    return {"status": "ok", "service": settings.app_name}


@app.get("/health")
async def health() -> dict[str, str]:
    """Lightweight liveness check that does not touch external systems."""

    return {"status": "healthy", "service": settings.app_name}


@app.get("/ready")
async def ready(request: Request) -> JSONResponse:
    """Readiness check that verifies MongoDB connectivity."""

    try:
        await request.app.state.mongo_client.admin.command("ping")
    except Exception as exc:  # noqa: BLE001 - surface readiness failures cleanly.
        return JSONResponse(
            status_code=503,
            content={"status": "unready", "service": settings.app_name, "detail": str(exc)},
        )

    return JSONResponse(status_code=200, content={"status": "ready", "service": settings.app_name})
