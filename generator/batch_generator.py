"""Generate and seed batches of MCQs using an LLM.

This script is intentionally standalone so it can be used for one-off dataset
seeding. It talks to any OpenAI-compatible API through the app's provider
layer; the default is Gemini's free tier via GEMINI_API_KEY.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import app.config  # noqa: F401  (loads .env into the environment)
from app.database import ensure_beanie_initialized, init_db
from app.llm.openai_compat import OpenAICompatibleProvider
from app.llm.registry import GEMINI_OPENAI_BASE_URL
from app.models.question import Question
from app.services.generation import generate_questions


async def seed_questions(topic: str, count: int, model: str, base_url: str, api_key_env: str) -> int:
    """Generate questions and persist them to MongoDB."""

    api_key = os.getenv(api_key_env)
    if not api_key:
        raise RuntimeError(f"{api_key_env} is not set.")

    provider = OpenAICompatibleProvider(base_url=base_url, api_key=api_key, model=model)
    generated_questions = await generate_questions(provider, topic, count)

    client = await init_db()
    try:
        await ensure_beanie_initialized(client)
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
    parser.add_argument("--model", default=os.getenv("LLM_MODEL", "gemini-2.5-flash"), help="Model name.")
    parser.add_argument(
        "--base-url",
        default=os.getenv("LLM_BASE_URL", GEMINI_OPENAI_BASE_URL),
        help="OpenAI-compatible base URL (default: Gemini).",
    )
    parser.add_argument(
        "--api-key-env",
        default=os.getenv("LLM_API_KEY_ENV", "GEMINI_API_KEY"),
        help="Name of the environment variable holding the API key.",
    )
    args = parser.parse_args()

    inserted_count = await seed_questions(args.topic, args.count, args.model, args.base_url, args.api_key_env)
    print(json.dumps({"inserted_count": inserted_count, "topic": args.topic}, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
