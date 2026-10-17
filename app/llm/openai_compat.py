"""Provider for any OpenAI-compatible chat completions API.

Gemini, OpenRouter, Groq, Ollama and OpenAI all speak this protocol; only the
base URL, model name and API key differ.
"""

from __future__ import annotations

from openai import APIError, AsyncOpenAI

from app.llm.base import LLMError, LLMResult


class OpenAICompatibleProvider:
    def __init__(self, base_url: str | None, api_key: str, model: str, timeout: float = 120.0) -> None:
        self._client = AsyncOpenAI(base_url=base_url, api_key=api_key, timeout=timeout, max_retries=2)
        self._model = model

    async def generate(self, system: str, user: str, json_mode: bool = True) -> LLMResult:
        kwargs = {"response_format": {"type": "json_object"}} if json_mode else {}
        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                temperature=0.7,
                **kwargs,
            )
        except APIError as exc:
            raise LLMError(f"{type(exc).__name__}: {exc}") from exc

        if not response.choices:
            raise LLMError("Provider returned no choices.")
        usage = response.usage
        return LLMResult(
            text=response.choices[0].message.content or "",
            input_tokens=usage.prompt_tokens if usage else None,
            output_tokens=usage.completion_tokens if usage else None,
        )
