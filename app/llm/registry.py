"""Build providers from stored LLM configs and seed the default configs."""

from __future__ import annotations

import os

from app.llm.base import LLMError, LLMProvider
from app.llm.openai_compat import OpenAICompatibleProvider
from app.models.llm_config import LLMConfig

GEMINI_OPENAI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"

DEFAULT_CONFIGS = [
    {
        "name": "Gemini Flash (free)",
        "provider": "openai_compat",
        "base_url": GEMINI_OPENAI_BASE_URL,
        "model": "gemini-flash-latest",  # alias tracks the current Flash model
        "api_key_env": "GEMINI_API_KEY",
        "is_free": True,
        "is_default": True,
    },
]


def build_provider(config: LLMConfig) -> LLMProvider:
    """Instantiate the provider described by `config`; the key comes from the environment."""

    if not config.enabled:
        raise LLMError(f"LLM config '{config.name}' is disabled.")
    api_key = os.getenv(config.api_key_env)
    if not api_key:
        raise LLMError(f"Environment variable {config.api_key_env} is not set.")
    if config.provider == "openai_compat":
        return OpenAICompatibleProvider(base_url=config.base_url, api_key=api_key, model=config.model)
    raise LLMError(f"Unsupported provider '{config.provider}'.")


async def get_default_config() -> LLMConfig:
    config = await LLMConfig.find_one(LLMConfig.is_default == True, LLMConfig.enabled == True)  # noqa: E712
    if config is None:
        config = await LLMConfig.find_one(LLMConfig.enabled == True)  # noqa: E712
    if config is None:
        raise LLMError("No enabled LLM config exists.")
    return config


async def seed_default_configs() -> None:
    """Insert the built-in configs when the collection is empty."""

    if await LLMConfig.find_all().count() == 0:
        await LLMConfig.insert_many([LLMConfig(**c) for c in DEFAULT_CONFIGS])
