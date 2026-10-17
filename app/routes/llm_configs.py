"""Admin endpoints for managing and testing LLM configs."""

import os
import time

from beanie import PydanticObjectId
from fastapi import APIRouter, Depends, HTTPException, Request
from pymongo.errors import DuplicateKeyError, ServerSelectionTimeoutError

from app.auth import require_admin
from app.database import ensure_beanie_initialized
from app.llm.base import LLMError
from app.llm.registry import build_provider
from app.models.llm_config import LLMConfig
from app.schemas.llm_config_schema import (
    LLMConfigCreate,
    LLMConfigRead,
    LLMConfigUpdate,
    LLMTestRequest,
    LLMTestResponse,
)
from app.schemas.question_schema import DeletedResponse

router = APIRouter(prefix="/api/llm-configs", tags=["llm"], dependencies=[Depends(require_admin)])


def _serialize(config: LLMConfig) -> LLMConfigRead:
    return LLMConfigRead(
        id=str(config.id),
        name=config.name,
        provider=config.provider,
        base_url=config.base_url,
        model=config.model,
        api_key_env=config.api_key_env,
        api_key_set=bool(os.getenv(config.api_key_env)),
        is_free=config.is_free,
        enabled=config.enabled,
        is_default=config.is_default,
        created_at=config.created_at,
    )


async def _load(request: Request, config_id: str) -> LLMConfig:
    await ensure_beanie_initialized(request.app.state.mongo_client)
    config = await LLMConfig.get(config_id) if PydanticObjectId.is_valid(config_id) else None
    if config is None:
        raise HTTPException(status_code=404, detail="LLM config not found")
    return config


async def _clear_other_defaults(keep_id) -> None:
    await LLMConfig.get_motor_collection().update_many(
        {"_id": {"$ne": keep_id}, "is_default": True}, {"$set": {"is_default": False}}
    )


@router.get("", response_model=list[LLMConfigRead])
async def list_configs(request: Request) -> list[LLMConfigRead]:
    try:
        await ensure_beanie_initialized(request.app.state.mongo_client)
        configs = await LLMConfig.find_all().sort("name").to_list()
    except ServerSelectionTimeoutError as exc:
        raise HTTPException(status_code=503, detail="MongoDB is unavailable.") from exc
    return [_serialize(c) for c in configs]


@router.post("", response_model=LLMConfigRead, status_code=201)
async def create_config(request: Request, body: LLMConfigCreate) -> LLMConfigRead:
    try:
        await ensure_beanie_initialized(request.app.state.mongo_client)
        config = LLMConfig(**body.model_dump())
        await config.insert()
        if config.is_default:
            await _clear_other_defaults(config.id)
    except DuplicateKeyError as exc:
        raise HTTPException(status_code=409, detail="An LLM config with this name already exists") from exc
    except ServerSelectionTimeoutError as exc:
        raise HTTPException(status_code=503, detail="MongoDB is unavailable.") from exc
    return _serialize(config)


@router.patch("/{config_id}", response_model=LLMConfigRead)
async def update_config(request: Request, config_id: str, body: LLMConfigUpdate) -> LLMConfigRead:
    try:
        config = await _load(request, config_id)
        for key, value in body.model_dump(exclude_unset=True).items():
            setattr(config, key, value)
        await config.save()
        if config.is_default:
            await _clear_other_defaults(config.id)
    except DuplicateKeyError as exc:
        raise HTTPException(status_code=409, detail="An LLM config with this name already exists") from exc
    except ServerSelectionTimeoutError as exc:
        raise HTTPException(status_code=503, detail="MongoDB is unavailable.") from exc
    return _serialize(config)


@router.delete("/{config_id}", response_model=DeletedResponse)
async def delete_config(request: Request, config_id: str) -> DeletedResponse:
    try:
        config = await _load(request, config_id)
        await config.delete()
    except ServerSelectionTimeoutError as exc:
        raise HTTPException(status_code=503, detail="MongoDB is unavailable.") from exc
    return DeletedResponse(deleted_id=config_id)


@router.post("/{config_id}/test", response_model=LLMTestResponse)
async def test_config(request: Request, config_id: str, body: LLMTestRequest | None = None) -> LLMTestResponse:
    """Send a tiny prompt to check the key, model name and JSON mode work."""

    config = await _load(request, config_id)
    prompt = (body or LLMTestRequest()).prompt
    started = time.perf_counter()
    try:
        result = await build_provider(config).generate("You are a connectivity test. Reply with JSON only.", prompt)
    except LLMError as exc:
        return LLMTestResponse(ok=False, latency_ms=int((time.perf_counter() - started) * 1000), error=str(exc))
    return LLMTestResponse(
        ok=True,
        latency_ms=int((time.perf_counter() - started) * 1000),
        output=result.text[:2000],
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
    )
