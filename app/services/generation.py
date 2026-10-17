"""Turn study notes or a topic description into validated draft MCQs."""

from __future__ import annotations

import asyncio
import difflib
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime

from beanie import PydanticObjectId
from pydantic import ValidationError

from app.llm.base import LLMError, LLMProvider
from app.llm.json_utils import extract_json
from app.llm.registry import build_provider
from app.models.generation_job import GenerationJob
from app.models.llm_config import LLMConfig
from app.models.note import Note
from app.models.prompt_template import PromptTemplate
from app.models.question import Question
from app.schemas.question_schema import GeneratedQuestionBatch, QuestionCreate

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = "You generate study content for an MCQ practice app. Return a single JSON object and nothing else."

MAX_CHUNK_CHARS = 12_000
DUPLICATE_THRESHOLD = 0.85
RAW_OUTPUT_LIMIT = 20_000

DEFAULT_TEMPLATE_NAME = "Interview MCQs"
DEFAULT_SYSTEM_PROMPT = """You are a senior technical interviewer writing multiple-choice questions that help a candidate retain what they studied.
Return a single JSON object and nothing else - no markdown fences, no commentary."""
DEFAULT_USER_PROMPT = """Write {{count}} multiple-choice questions.

Topic: {{topic}}
Subtopic: {{subtopic}}
Difficulty: {{difficulty}}
Focus: {{focus}}

Source notes:
<<<NOTES
{{notes}}
NOTES>>>

Rules:
- {{knowledge_rule}}
- Test understanding and application, not recall of exact wording.
- Mix question styles: concepts, "what does this code print/do", scenario and trade-off questions, edge cases.
- Every question has exactly 4 options with indexes 0, 1, 2, 3. Vary which index is correct.
- Wrong options must be plausible and based on common misconceptions; avoid "all of the above".
- Use more than one correct option only when the question text says "Select all that apply".
- The explanation says why the correct option(s) are right and briefly why each wrong option is wrong.
- Put code in the question text using markdown code fences inside the JSON string.
- No two questions may test the same fact.

Additional instructions: {{extra_instructions}}

Return JSON matching this schema:
{{schema}}"""

_DIFFICULTY_TEXT = {
    "MIXED": "a mix of EASY, MEDIUM and HARD (roughly 30/50/20)",
    "EASY": "EASY",
    "MEDIUM": "MEDIUM",
    "HARD": "HARD",
}

# Keep references to running tasks so they are not garbage-collected mid-run.
_running_tasks: set[asyncio.Task] = set()


# ---------------------------------------------------------------- prompting


def schema_hint() -> str:
    return json.dumps(GeneratedQuestionBatch.model_json_schema(), indent=2, ensure_ascii=True)


def render(template: str, values: dict[str, str]) -> str:
    """Replace {{name}} placeholders; unknown placeholders are left untouched."""

    return re.sub(r"\{\{\s*(\w+)\s*\}\}", lambda m: values.get(m.group(1), m.group(0)), template)


def build_prompt(topic: str, count: int) -> str:
    """Prompt used by the standalone generator script (no notes)."""

    return render(
        DEFAULT_USER_PROMPT,
        _prompt_values(topic, topic, count, "MIXED", notes="", focus=topic, extra="", outside=True),
    )


def _prompt_values(
    topic: str, subtopic: str, count: int, difficulty: str, notes: str, focus: str, extra: str, outside: bool
) -> dict[str, str]:
    if notes:
        rule = (
            "Base questions on the source notes; you may add closely related standard facts."
            if outside
            else "Use only facts stated in the source notes. Do not introduce outside facts."
        )
    else:
        rule = "No notes were provided: write questions from well-established knowledge of the focus."
    return {
        "topic": topic,
        "subtopic": subtopic,
        "count": str(count),
        "difficulty": _DIFFICULTY_TEXT.get(difficulty, difficulty),
        "notes": notes or "(none)",
        "focus": focus or "(the whole subtopic)",
        "extra_instructions": extra or "(none)",
        "knowledge_rule": rule,
        "schema": schema_hint(),
    }


def chunk_text(text: str, max_chars: int = MAX_CHUNK_CHARS) -> list[str]:
    """Split text on paragraph boundaries into chunks of at most ~max_chars."""

    if len(text) <= max_chars:
        return [text]
    chunks: list[str] = []
    current = ""
    for para in re.split(r"\n\s*\n", text):
        while len(para) > max_chars:  # a single huge paragraph
            if current:
                chunks.append(current)
                current = ""
            chunks.append(para[:max_chars])
            para = para[max_chars:]
        if current and len(current) + len(para) + 2 > max_chars:
            chunks.append(current)
            current = para
        else:
            current = f"{current}\n\n{para}" if current else para
    if current:
        chunks.append(current)
    return chunks


def split_count(total: int, parts: int) -> list[int]:
    """Distribute `total` questions over `parts` chunks, dropping chunks that get zero."""

    base, extra = divmod(total, parts)
    return [base + (1 if i < extra else 0) for i in range(parts)]


# ---------------------------------------------------------------- LLM call


@dataclass
class CallOutcome:
    questions: list[QuestionCreate]
    input_tokens: int = 0
    output_tokens: int = 0
    raw: list[str] = field(default_factory=list)


class GenerationFailed(LLMError):
    def __init__(self, message: str, outcome: "CallOutcome"):
        super().__init__(message)
        self.raw = outcome.raw
        self.input_tokens = outcome.input_tokens
        self.output_tokens = outcome.output_tokens


def parse_batch(text: str) -> list[QuestionCreate]:
    return GeneratedQuestionBatch.model_validate_json(extract_json(text)).questions


async def call_and_parse(provider: LLMProvider, system: str, user: str) -> CallOutcome:
    """Call the model and validate; retry once with the validation error if parsing fails."""

    outcome = CallOutcome(questions=[])
    result = await provider.generate(system, user)
    outcome.raw.append(result.text)
    outcome.input_tokens += result.input_tokens or 0
    outcome.output_tokens += result.output_tokens or 0
    try:
        outcome.questions = parse_batch(result.text)
        return outcome
    except (ValidationError, ValueError) as exc:
        repair = (
            f"{user}\n\nYour previous reply was invalid:\n{str(exc)[:2000]}\n\n"
            f"Previous reply:\n{result.text[:8000]}\n\nReturn the corrected JSON object only."
        )
    retry = await provider.generate(system, repair)
    outcome.raw.append(retry.text)
    outcome.input_tokens += retry.input_tokens or 0
    outcome.output_tokens += retry.output_tokens or 0
    try:
        outcome.questions = parse_batch(retry.text)
        return outcome
    except (ValidationError, ValueError) as exc:
        raise GenerationFailed(f"Model output failed validation twice: {str(exc)[:500]}", outcome) from exc


async def generate_questions(provider: LLMProvider, topic: str, count: int) -> list[QuestionCreate]:
    """Generate questions for a topic without notes (used by the generator script)."""

    return (await call_and_parse(provider, SYSTEM_PROMPT, build_prompt(topic, count))).questions


# ---------------------------------------------------------------- dedupe


def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def is_duplicate(text: str, existing: list[str], threshold: float = DUPLICATE_THRESHOLD) -> bool:
    norm = _normalize(text)
    return any(difflib.SequenceMatcher(None, norm, other).ratio() >= threshold for other in existing)


async def _existing_texts(topic: str, subtopic: str) -> list[str]:
    docs = await Question.get_motor_collection().find(
        {"topic": topic, "subtopic": subtopic, "status": {"$ne": "rejected"}}, {"question_text": 1}
    ).to_list(length=None)
    return [_normalize(d["question_text"]) for d in docs]


# ---------------------------------------------------------------- templates


async def seed_default_template() -> None:
    if await PromptTemplate.find_all().count() == 0:
        await PromptTemplate(
            name=DEFAULT_TEMPLATE_NAME,
            system_prompt=DEFAULT_SYSTEM_PROMPT,
            user_prompt=DEFAULT_USER_PROMPT,
            is_default=True,
        ).insert()


async def get_default_template() -> PromptTemplate:
    template = await PromptTemplate.find_one(PromptTemplate.is_default == True)  # noqa: E712
    if template is None:
        template = await PromptTemplate.find_all().sort("-created_at").first_or_none()
    if template is None:
        raise LLMError("No prompt template exists.")
    return template


# ---------------------------------------------------------------- jobs


async def _job_context(job: GenerationJob) -> tuple[LLMProvider, PromptTemplate, str]:
    config = await LLMConfig.get(job.llm_config_id)
    if config is None:
        raise LLMError("The LLM config used by this job no longer exists.")
    template = await PromptTemplate.get(job.prompt_template_id)
    if template is None:
        raise LLMError("The prompt template used by this job no longer exists.")
    notes = await Note.find({"_id": {"$in": job.note_ids}}).to_list() if job.note_ids else []
    notes_text = "\n\n".join(f"## {n.title}\n\n{n.content}" for n in notes)
    return build_provider(config), template, notes_text


def _to_draft(q: QuestionCreate, job: GenerationJob) -> Question:
    data = q.model_dump()
    data.update(topic=job.topic, subtopic=job.subtopic)
    if data.get("difficulty") not in ("EASY", "MEDIUM", "HARD"):
        data["difficulty"] = "MEDIUM"
    return Question(**data, status="draft", source_note_ids=job.note_ids, generation_job_id=job.id)


async def run_job(job_id: PydanticObjectId) -> None:
    """Execute a queued job: generate, dedupe, and store questions as drafts."""

    job = await GenerationJob.get(job_id)
    if job is None:
        return
    job.status = "running"
    job.started_at = datetime.now(UTC)
    await job.save()

    raw: list[str] = []
    try:
        provider, template, notes_text = await _job_context(job)
        chunks = chunk_text(notes_text) if notes_text else [""]
        counts = split_count(job.params.count, len(chunks))
        existing = await _existing_texts(job.topic, job.subtopic)

        drafts: list[Question] = []
        for chunk, count in zip(chunks, counts):
            if count == 0:
                continue
            values = _prompt_values(
                job.topic,
                job.subtopic,
                count,
                job.params.difficulty,
                notes=chunk,
                focus=job.focus or "",
                extra=job.extra_instructions or "",
                outside=job.params.allow_outside_knowledge,
            )
            outcome = await call_and_parse(provider, template.system_prompt, render(template.user_prompt, values))
            raw = outcome.raw
            job.input_tokens += outcome.input_tokens
            job.output_tokens += outcome.output_tokens
            for q in outcome.questions:
                if is_duplicate(q.question_text, existing):
                    job.duplicates_skipped += 1
                    continue
                existing.append(_normalize(q.question_text))
                drafts.append(_to_draft(q, job))

        if drafts:
            result = await Question.insert_many(drafts)
            job.created_question_ids = list(result.inserted_ids)
        job.status = "succeeded"
    except Exception as exc:  # noqa: BLE001 - every failure is recorded on the job
        logger.exception("Generation job %s failed", job_id)
        job.status = "failed"
        job.error = str(exc)[:2000]
        raw = getattr(exc, "raw", raw)
        job.input_tokens += getattr(exc, "input_tokens", 0)
        job.output_tokens += getattr(exc, "output_tokens", 0)
        job.raw_output = "\n\n---\n\n".join(raw)[:RAW_OUTPUT_LIMIT] or None
    job.finished_at = datetime.now(UTC)
    await job.save()


def start_job(job_id: PydanticObjectId) -> None:
    task = asyncio.create_task(run_job(job_id))
    _running_tasks.add(task)
    task.add_done_callback(_running_tasks.discard)


async def recover_interrupted_jobs() -> None:
    """Jobs left queued/running by a previous process can never finish; mark them failed."""

    await GenerationJob.get_motor_collection().update_many(
        {"status": {"$in": ["queued", "running"]}},
        {"$set": {"status": "failed", "error": "Interrupted by a server restart. Start the job again.",
                  "finished_at": datetime.now(UTC)}},
    )


async def regenerate_question(question: Question) -> Question:
    """Replace one draft with a freshly generated draft from the same job context."""

    job = await GenerationJob.get(question.generation_job_id) if question.generation_job_id else None
    if job is None:
        raise LLMError("This question was not generated by a job, so it cannot be regenerated.")

    provider, template, notes_text = await _job_context(job)
    existing = await _existing_texts(job.topic, job.subtopic)
    extra = (
        f"{job.extra_instructions or ''}\nWrite a different question from this rejected one: "
        f"\"{question.question_text[:500]}\""
    ).strip()
    values = _prompt_values(
        job.topic, job.subtopic, 1, question.difficulty if question.difficulty in _DIFFICULTY_TEXT else "MIXED",
        notes=chunk_text(notes_text)[0] if notes_text else "", focus=job.focus or "", extra=extra,
        outside=job.params.allow_outside_knowledge,
    )
    outcome = await call_and_parse(provider, template.system_prompt, render(template.user_prompt, values))
    candidates = [q for q in outcome.questions if not is_duplicate(q.question_text, existing)] or outcome.questions
    if not candidates:
        raise LLMError("The model returned no question.")

    new = _to_draft(candidates[0], job)
    await new.insert()
    await question.delete()
    await GenerationJob.get_motor_collection().update_one(
        {"_id": job.id},
        {"$pull": {"created_question_ids": question.id}, "$inc": {
            "input_tokens": outcome.input_tokens, "output_tokens": outcome.output_tokens}},
    )
    await GenerationJob.get_motor_collection().update_one(
        {"_id": job.id}, {"$push": {"created_question_ids": new.id}}
    )
    return new
