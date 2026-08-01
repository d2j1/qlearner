"""MongoDB and Beanie initialization helpers."""

from __future__ import annotations

import asyncio
from typing import Optional

from beanie import init_beanie
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.config import get_settings
from app.models.question import Question

_beanie_initialized = False
_beanie_lock = asyncio.Lock()


def create_db_client() -> AsyncIOMotorClient:
    """Create a Mongo client without forcing a network connection."""

    settings = get_settings()
    return AsyncIOMotorClient(settings.mongo_url)


def get_database(client: AsyncIOMotorClient) -> AsyncIOMotorDatabase:
    """Return the configured database, falling back to mcq_db if needed."""

    database = client.get_default_database()
    if database is None:
        database = client["mcq_db"]
    return database


async def ensure_beanie_initialized(client: AsyncIOMotorClient) -> None:
    """Initialize Beanie once, on demand, when a DB-backed request arrives."""

    global _beanie_initialized
    if _beanie_initialized:
        return

    async with _beanie_lock:
        if _beanie_initialized:
            return

        await init_beanie(database=get_database(client), document_models=[Question])
        _beanie_initialized = True


def reset_beanie_state() -> None:
    """Reset the lazy-init flag during shutdown or tests."""

    global _beanie_initialized
    _beanie_initialized = False
