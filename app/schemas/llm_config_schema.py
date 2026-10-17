"""Request and response schemas for LLM configs."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

Provider = Literal["openai_compat"]


class LLMConfigCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    provider: Provider = "openai_compat"
    base_url: str | None = None
    model: str = Field(min_length=1)
    api_key_env: str = Field(pattern=r"^[A-Z][A-Z0-9_]*$")
    is_free: bool = False
    enabled: bool = True
    is_default: bool = False


class LLMConfigUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    base_url: str | None = None
    model: str | None = Field(default=None, min_length=1)
    api_key_env: str | None = Field(default=None, pattern=r"^[A-Z][A-Z0-9_]*$")
    is_free: bool | None = None
    enabled: bool | None = None
    is_default: bool | None = None


class LLMConfigRead(BaseModel):
    id: str
    name: str
    provider: str
    base_url: str | None
    model: str
    api_key_env: str
    api_key_set: bool
    is_free: bool
    enabled: bool
    is_default: bool
    created_at: datetime


class LLMTestRequest(BaseModel):
    prompt: str = Field(default="Reply with a JSON object {\"ok\": true, \"model\": \"<your model name>\"}.", max_length=2000)


class LLMTestResponse(BaseModel):
    ok: bool
    latency_ms: int
    output: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    error: str | None = None
