"""Beanie document model for selectable LLM configurations."""

from datetime import UTC, datetime

from beanie import Document, Indexed
from pydantic import Field


class LLMConfig(Document):
    """A model the app can generate with.

    Only the *name* of the environment variable holding the API key is stored,
    never the key itself.
    """

    name: Indexed(str, unique=True)
    provider: str = "openai_compat"
    base_url: str | None = None
    model: str
    api_key_env: str
    is_free: bool = False
    enabled: bool = True
    is_default: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    class Settings:
        name = "llm_configs"
