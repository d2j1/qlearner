"""Turn a topic description into validated MCQs using any LLM provider."""

from __future__ import annotations

import json

from pydantic import ValidationError

from app.llm.base import LLMError, LLMProvider
from app.llm.json_utils import extract_json
from app.schemas.question_schema import GeneratedQuestionBatch, QuestionCreate

SYSTEM_PROMPT = "You generate study content for an MCQ practice app. Return a single JSON object and nothing else."


def build_prompt(topic: str, count: int) -> str:
    """Create a strict prompt that asks the model for JSON only."""

    schema_hint = json.dumps(GeneratedQuestionBatch.model_json_schema(), indent=2, ensure_ascii=True)
    return f"""Return JSON only. Do not wrap the output in markdown fences.

Topic: {topic}
Number of questions: {count}

Required structure:
{schema_hint}

Rules:
- Every question must have exactly 4 options.
- Option indexes must be 0, 1, 2, and 3.
- correct_option_indices must contain one or more of those values.
- difficulty should be one of EASY, MEDIUM, or HARD.
- explanations must clearly justify why the correct answer is right.
- Keep each question unique, factual, and appropriate for practice use.
"""


def parse_batch(text: str) -> list[QuestionCreate]:
    return GeneratedQuestionBatch.model_validate_json(extract_json(text)).questions


async def generate_questions(provider: LLMProvider, topic: str, count: int) -> list[QuestionCreate]:
    """Generate and validate questions, retrying once with the validation error if parsing fails."""

    prompt = build_prompt(topic, count)
    result = await provider.generate(SYSTEM_PROMPT, prompt)
    try:
        return parse_batch(result.text)
    except (ValidationError, ValueError) as exc:
        repair = (
            f"{prompt}\n\nYour previous reply was invalid:\n{str(exc)[:2000]}\n\n"
            f"Previous reply:\n{result.text[:8000]}\n\nReturn the corrected JSON object only."
        )
        retry = await provider.generate(SYSTEM_PROMPT, repair)
        try:
            return parse_batch(retry.text)
        except (ValidationError, ValueError) as retry_exc:
            raise LLMError(f"Model output failed validation twice: {str(retry_exc)[:500]}") from retry_exc
