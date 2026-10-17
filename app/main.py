"""FastAPI application entry point."""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pymongo.errors import ServerSelectionTimeoutError

from app.config import get_settings
from app.database import create_db_client, ensure_beanie_initialized, reset_beanie_state
from app.routes.auth import router as auth_router
from app.routes.generation import router as generation_router
from app.routes.llm_configs import router as llm_configs_router
from app.routes.notes import router as notes_router
from app.routes.prompts import router as prompts_router
from app.routes.questions import router as questions_router
from app.services.generation import recover_interrupted_jobs


async def _recover_jobs(app: FastAPI) -> None:
    """Fail jobs a previous process left unfinished. Runs in the background so a
    slow or offline MongoDB never blocks startup."""

    try:
        await ensure_beanie_initialized(app.state.mongo_client)
        await recover_interrupted_jobs()
    except Exception:  # noqa: BLE001
        logging.getLogger(__name__).warning("Could not recover interrupted generation jobs", exc_info=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create the Mongo client on startup and close it on shutdown.

    Beanie initialization is deferred until a request actually touches the
    database so the process can boot even when MongoDB is temporarily offline.
    """

    app.state.mongo_client = create_db_client()
    recovery = asyncio.create_task(_recover_jobs(app))
    yield
    recovery.cancel()
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

app.include_router(auth_router)
# generation_router goes before questions_router so /api/questions/drafts and
# /api/questions/approve are matched before /api/questions/{question_id}.
app.include_router(generation_router)
app.include_router(questions_router)
app.include_router(llm_configs_router)
app.include_router(notes_router)
app.include_router(prompts_router)


@app.exception_handler(ServerSelectionTimeoutError)
async def mongo_unavailable(_request: Request, _exc: ServerSelectionTimeoutError) -> JSONResponse:
    return JSONResponse(status_code=503, content={"detail": "MongoDB is unavailable."})


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
