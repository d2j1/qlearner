"""Admin endpoints for generation jobs and reviewing the drafts they create."""

from beanie import PydanticObjectId
from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth import require_admin
from app.llm.base import LLMError
from app.llm.registry import get_default_config
from app.models.generation_job import GenerationJob, GenerationParams
from app.models.llm_config import LLMConfig
from app.models.note import Note
from app.models.prompt_template import PromptTemplate
from app.models.question import Question
from app.routes.common import get_or_404, parse_object_ids
from app.routes.questions import _serialize_question
from app.schemas.generation_schema import GenerationJobCreate, GenerationJobListResponse, GenerationJobRead
from app.schemas.question_schema import BulkStatusResponse, IdsRequest, QuestionListResponse, QuestionRead
from app.services.generation import get_default_template, regenerate_question, start_job

router = APIRouter(tags=["generation"], dependencies=[Depends(require_admin)])


def _job_read(job: GenerationJob) -> GenerationJobRead:
    return GenerationJobRead(
        id=str(job.id),
        topic=job.topic,
        subtopic=job.subtopic,
        note_ids=[str(i) for i in job.note_ids],
        focus=job.focus,
        extra_instructions=job.extra_instructions,
        count=job.params.count,
        difficulty=job.params.difficulty,
        allow_outside_knowledge=job.params.allow_outside_knowledge,
        llm_config_id=str(job.llm_config_id),
        llm_model=job.llm_model,
        prompt_template_id=str(job.prompt_template_id),
        prompt_template_version=job.prompt_template_version,
        status=job.status,
        created_question_ids=[str(i) for i in job.created_question_ids],
        created_count=len(job.created_question_ids),
        duplicates_skipped=job.duplicates_skipped,
        error=job.error,
        raw_output=job.raw_output,
        input_tokens=job.input_tokens,
        output_tokens=job.output_tokens,
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
    )


# ---------------------------------------------------------------- jobs


@router.post("/api/generation/jobs", response_model=GenerationJobRead, status_code=202)
async def create_job(body: GenerationJobCreate) -> GenerationJobRead:
    """Queue a generation run. Poll GET /api/generation/jobs/{id} until it finishes."""

    note_ids = parse_object_ids(body.note_ids, "note")
    if note_ids:
        found = await Note.get_motor_collection().count_documents({"_id": {"$in": note_ids}})
        if found != len(set(note_ids)):
            raise HTTPException(status_code=404, detail="One or more notes not found")

    try:
        config = (
            await get_or_404(LLMConfig, body.llm_config_id, "LLM config")
            if body.llm_config_id
            else await get_default_config()
        )
        template = (
            await get_or_404(PromptTemplate, body.prompt_template_id, "Prompt template")
            if body.prompt_template_id
            else await get_default_template()
        )
    except LLMError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not config.enabled:
        raise HTTPException(status_code=409, detail=f"LLM config '{config.name}' is disabled")

    job = GenerationJob(
        topic=body.topic.strip(),
        subtopic=body.subtopic.strip(),
        note_ids=note_ids,
        focus=body.focus,
        extra_instructions=body.extra_instructions,
        params=GenerationParams(
            count=body.count, difficulty=body.difficulty, allow_outside_knowledge=body.allow_outside_knowledge
        ),
        llm_config_id=config.id,
        llm_model=config.model,
        prompt_template_id=template.id,
        prompt_template_version=template.version,
    )
    await job.insert()
    start_job(job.id)
    return _job_read(job)


@router.get("/api/generation/jobs", response_model=GenerationJobListResponse)
async def list_jobs(
    status: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> GenerationJobListResponse:
    query = {"status": status} if status else {}
    total = await GenerationJob.get_motor_collection().count_documents(query)
    jobs = await GenerationJob.find(query).sort("-created_at").skip(offset).limit(limit).to_list()
    return GenerationJobListResponse(total=total, limit=limit, offset=offset, items=[_job_read(j) for j in jobs])


@router.get("/api/generation/jobs/{job_id}", response_model=GenerationJobRead)
async def get_job(job_id: str) -> GenerationJobRead:
    return _job_read(await get_or_404(GenerationJob, job_id, "Generation job"))


# ---------------------------------------------------------------- drafts


@router.get("/api/questions/drafts", response_model=QuestionListResponse)
async def list_drafts(
    job_id: str | None = None,
    topic: str | None = None,
    subtopic: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> QuestionListResponse:
    query: dict = {"status": "draft"}
    if job_id:
        query["generation_job_id"] = parse_object_ids([job_id], "job")[0]
    if topic is not None:
        query["topic"] = topic
    if subtopic is not None:
        query["subtopic"] = subtopic
    total = await Question.get_motor_collection().count_documents(query)
    docs = await Question.find(query).sort("created_at").skip(offset).limit(limit).to_list()
    return QuestionListResponse(
        total=total, limit=limit, offset=offset, items=[_serialize_question(d) for d in docs]
    )


async def _set_status(ids: list[PydanticObjectId], status: str) -> int:
    result = await Question.get_motor_collection().update_many(
        {"_id": {"$in": ids}, "status": {"$ne": status}}, {"$set": {"status": status}}
    )
    return int(result.modified_count)


@router.post("/api/questions/approve", response_model=BulkStatusResponse)
async def approve_many(body: IdsRequest) -> BulkStatusResponse:
    return BulkStatusResponse(modified_count=await _set_status(parse_object_ids(body.ids, "question"), "approved"))


@router.post("/api/questions/reject", response_model=BulkStatusResponse)
async def reject_many(body: IdsRequest) -> BulkStatusResponse:
    return BulkStatusResponse(modified_count=await _set_status(parse_object_ids(body.ids, "question"), "rejected"))


@router.post("/api/questions/{question_id}/approve", response_model=QuestionRead)
async def approve_one(question_id: str) -> QuestionRead:
    question = await get_or_404(Question, question_id, "Question")
    question.status = "approved"
    await question.save()
    return _serialize_question(question)


@router.post("/api/questions/{question_id}/reject", response_model=QuestionRead)
async def reject_one(question_id: str) -> QuestionRead:
    question = await get_or_404(Question, question_id, "Question")
    question.status = "rejected"
    await question.save()
    return _serialize_question(question)


@router.post("/api/questions/{question_id}/regenerate", response_model=QuestionRead)
async def regenerate_one(question_id: str) -> QuestionRead:
    """Replace a draft with a new one from the same job. Waits for the model (~10-20 s)."""

    question = await get_or_404(Question, question_id, "Question")
    if question.status != "draft":
        raise HTTPException(status_code=409, detail="Only draft questions can be regenerated")
    try:
        new = await regenerate_question(question)
    except LLMError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return _serialize_question(new)
