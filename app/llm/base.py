"""Provider-agnostic interface for calling an LLM."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class LLMError(RuntimeError):
    """Raised when a provider call fails or is misconfigured."""


@dataclass
class LLMResult:
    """Text returned by a provider plus token usage when the provider reports it."""

    text: str
    input_tokens: int | None = None
    output_tokens: int | None = None


class LLMProvider(Protocol):
    """Anything that can turn a system + user prompt into text."""

    async def generate(self, system: str, user: str, json_mode: bool = True) -> LLMResult: ...
