"""Generate and seed batches of MCQs using an LLM.

This script is intentionally standalone so it can be used for one-off dataset
seeding as well as repeatable content generation in development or staging.
It supports OpenAI by default and can also use Google's Gemini SDK when the
provider is set to ``gemini``.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Literal

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.database import init_db
from app.models.question import Question
from app.schemas.question_schema import GeneratedQuestionBatch, QuestionCreate


def build_prompt(topic: str, count: int) -> str:
    """Create a strict prompt that asks the model for JSON only."""

    schema_hint = json.dumps(
        GeneratedQuestionBatch.model_json_schema(),
        indent=2,
        ensure_ascii=True,
    )
    return f"""You are generating study content for an MCQ practice app.

Return JSON only. Do not wrap the output in markdown fences.

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


async def generate_with_openai(topic: str, count: int, model: str) -> list[QuestionCreate]:
    """Generate question payloads using the OpenAI API."""

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is required when provider=openai.")

    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=api_key)
    response = await client.responses.create(
        model=model,
        input=build_prompt(topic, count),
        temperature=0.7,
    )

    payload_text = response.output_text.strip()
    batch = GeneratedQuestionBatch.model_validate_json(payload_text)
    return batch.questions


async def generate_with_gemini(topic: str, count: int, model: str) -> list[QuestionCreate]:
    """Generate question payloads using Google's Gemini SDK."""

    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY or GOOGLE_API_KEY is required when provider=gemini.")

    def _generate_sync() -> str:
        import google.generativeai as genai

        genai.configure(api_key=api_key)
        llm = genai.GenerativeModel(model)
        response = llm.generate_content(build_prompt(topic, count))
        return response.text or ""

    payload_text = await asyncio.to_thread(_generate_sync)
    batch = GeneratedQuestionBatch.model_validate_json(payload_text)
    return batch.questions


async def seed_questions(topic: str, count: int, provider: Literal["openai", "gemini"], model: str) -> int:
    """Generate questions and persist them to MongoDB."""

    if provider == "gemini":
        generated_questions = await generate_with_gemini(topic, count, model)
    else:
        generated_questions = await generate_with_openai(topic, count, model)

    client = await init_db()
    try:
        documents = [Question(**question.model_dump()) for question in generated_questions]
        result = await Question.insert_many(documents)
        return len(result.inserted_ids)
    finally:
        client.close()


async def main() -> None:
    """Parse arguments, generate questions, and seed the database."""

    parser = argparse.ArgumentParser(description="Generate and seed MCQ questions.")
    parser.add_argument("--topic", required=True, help="Topic to generate questions for.")
    parser.add_argument("--count", type=int, default=10, help="Number of questions to generate.")
    parser.add_argument(
        "--provider",
        choices=("openai", "gemini"),
        default=os.getenv("LLM_PROVIDER", "openai"),
        help="LLM provider to use.",
    )
    parser.add_argument(
        "--model",
        default=os.getenv("LLM_MODEL", "gpt-4.1-mini"),
        help="LLM model name.",
    )
    args = parser.parse_args()

    inserted_count = await seed_questions(
        topic=args.topic,
        count=args.count,
        provider=args.provider,
        model=args.model,
    )
    print(json.dumps({"inserted_count": inserted_count, "topic": args.topic}, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
