"""Question and topic endpoints for the MCQ backend."""

import re
from collections import defaultdict

from beanie import PydanticObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pymongo.errors import ServerSelectionTimeoutError

from app.auth import require_admin
from app.database import ensure_beanie_initialized
from app.models.question import VISIBLE_FILTER, Question
from app.routes.common import get_or_404
from app.services.taxonomy import rename, taxonomy
from app.schemas.question_schema import (
    BulkQuestionResponse,
    DeletedResponse,
    RenameResponse,
    OptionSchema,
    QuestionCreate,
    QuestionListResponse,
    QuestionRead,
    QuestionUpdate,
    SubtopicGroup,
    SubtopicListResponse,
    SubtopicSummary,
    SubtopicRenameRequest,
    TaxonomyResponse,
    TopicListResponse,
    TopicQuestionsResponse,
    TopicRenameRequest,
    validate_correct_indices,
)

router = APIRouter(prefix="/api", tags=["questions"])


def _serialize_question(question: Question) -> QuestionRead:
    """Convert a Beanie document into the API response schema."""

    return QuestionRead(
        id=str(question.id) if question.id else None,
        topic=question.topic,
        subtopic=question.subtopic,
        question_text=question.question_text,
        options=[OptionSchema(index=o.index, text=o.text) for o in question.options],
        correct_option_indices=question.correct_option_indices,
        explanation=question.explanation,
        difficulty=question.difficulty,
        created_at=question.created_at,
        status=question.status,
        tags=question.tags,
        source_note_ids=[str(i) for i in question.source_note_ids],
        generation_job_id=str(question.generation_job_id) if question.generation_job_id else None,
    )


async def _count_and_load_questions(query: dict, limit: int, offset: int) -> tuple[int, list[Question]]:
    """Load questions and total count with the same filters."""

    total = await Question.get_motor_collection().count_documents(query)
    docs = await Question.find(query).skip(offset).limit(limit).to_list()
    return total, docs


@router.get("/topics", response_model=TopicListResponse)
async def get_topics(request: Request) -> TopicListResponse:
    """Return the distinct set of stored topics."""

    try:
        await ensure_beanie_initialized(request.app.state.mongo_client)
        topics = await Question.get_motor_collection().distinct("topic", VISIBLE_FILTER)
    except ServerSelectionTimeoutError as exc:
        raise HTTPException(status_code=503, detail="MongoDB is unavailable.") from exc

    return TopicListResponse(topics=sorted(topic for topic in topics if isinstance(topic, str) and topic))


@router.get("/questions", response_model=QuestionListResponse)
async def list_questions(
    request: Request,
    topic: str | None = Query(default=None),
    subtopic: str | None = Query(default=None),
    q: str | None = Query(default=None, max_length=200, description="Case-insensitive search in question text"),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> QuestionListResponse:
    """Return a flat list of questions, optionally filtered by topic/subtopic and text search."""

    try:
        await ensure_beanie_initialized(request.app.state.mongo_client)
        query: dict = dict(VISIBLE_FILTER)
        if topic is not None:
            query["topic"] = topic
        if subtopic is not None:
            query["subtopic"] = subtopic
        if q and q.strip():
            query["question_text"] = {"$regex": re.escape(q.strip()), "$options": "i"}
        total, docs = await _count_and_load_questions(query, limit, offset)
    except ServerSelectionTimeoutError as exc:
        raise HTTPException(status_code=503, detail="MongoDB is unavailable.") from exc

    return QuestionListResponse(
        total=total,
        limit=limit,
        offset=offset,
        items=[_serialize_question(doc) for doc in docs],
    )


@router.get("/topics/{topic}/subtopics", response_model=SubtopicListResponse)
async def get_subtopics(request: Request, topic: str) -> SubtopicListResponse:
    """Return the subtopics of a topic with their question counts."""

    try:
        await ensure_beanie_initialized(request.app.state.mongo_client)
        pipeline = [
            {"$match": {**VISIBLE_FILTER, "topic": topic}},
            {"$group": {"_id": "$subtopic", "count": {"$sum": 1}}},
            {"$sort": {"_id": 1}},
        ]
        rows = await Question.get_motor_collection().aggregate(pipeline).to_list(length=None)
    except ServerSelectionTimeoutError as exc:
        raise HTTPException(status_code=503, detail="MongoDB is unavailable.") from exc

    if not rows:
        raise HTTPException(status_code=404, detail="Topic not found")

    return SubtopicListResponse(
        topic=topic,
        subtopics=[SubtopicSummary(subtopic=row["_id"], question_count=row["count"]) for row in rows if row["_id"]],
    )


@router.get("/topics/{topic}/subtopics/{subtopic}/questions", response_model=QuestionListResponse)
async def get_questions_by_subtopic(
    request: Request,
    topic: str,
    subtopic: str,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> QuestionListResponse:
    """Return the practice questions for one subtopic of a topic."""

    try:
        await ensure_beanie_initialized(request.app.state.mongo_client)
        total, docs = await _count_and_load_questions(
            {**VISIBLE_FILTER, "topic": topic, "subtopic": subtopic}, limit, offset
        )
    except ServerSelectionTimeoutError as exc:
        raise HTTPException(status_code=503, detail="MongoDB is unavailable.") from exc

    return QuestionListResponse(
        total=total,
        limit=limit,
        offset=offset,
        items=[_serialize_question(doc) for doc in docs],
    )


@router.get("/topics/{topic}/questions", response_model=TopicQuestionsResponse)
async def get_questions_by_topic(
    request: Request,
    topic: str,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> TopicQuestionsResponse:
    """Return questions for a topic grouped by subtopic."""

    try:
        await ensure_beanie_initialized(request.app.state.mongo_client)
        total, docs = await _count_and_load_questions({**VISIBLE_FILTER, "topic": topic}, limit, offset)
    except ServerSelectionTimeoutError as exc:
        raise HTTPException(status_code=503, detail="MongoDB is unavailable.") from exc

    groups: dict[str, list[QuestionRead]] = defaultdict(list)
    for doc in docs:
        q = _serialize_question(doc)
        groups[q.subtopic].append(q)

    return TopicQuestionsResponse(
        topic=topic,
        total=total,
        limit=limit,
        offset=offset,
        groups=[SubtopicGroup(subtopic=sub, questions=qs) for sub, qs in groups.items()],
    )


@router.get("/questions/{question_id}", response_model=QuestionRead)
async def get_question_by_id(request: Request, question_id: str) -> QuestionRead:
    """Return one question by id."""

    try:
        await ensure_beanie_initialized(request.app.state.mongo_client)
        question = await get_or_404(Question, question_id, "Question")
    except ServerSelectionTimeoutError as exc:
        raise HTTPException(status_code=503, detail="MongoDB is unavailable.") from exc

    return _serialize_question(question)


@router.post("/questions/bulk", response_model=BulkQuestionResponse, status_code=201, dependencies=[Depends(require_admin)])
async def bulk_insert_questions(
    request: Request,
    questions: list[QuestionCreate],
) -> BulkQuestionResponse:
    """Insert a batch of questions in one database round-trip."""

    if not questions:
        raise HTTPException(status_code=400, detail="At least one question is required.")

    try:
        await ensure_beanie_initialized(request.app.state.mongo_client)
        documents = [Question(**question.model_dump()) for question in questions]
        result = await Question.insert_many(documents)
    except ServerSelectionTimeoutError as exc:
        raise HTTPException(status_code=503, detail="MongoDB is unavailable.") from exc

    inserted_ids = [str(inserted_id) for inserted_id in result.inserted_ids]
    return BulkQuestionResponse(
        inserted_count=len(inserted_ids),
        inserted_ids=inserted_ids,
    )


@router.patch("/questions/{question_id}", response_model=QuestionRead, dependencies=[Depends(require_admin)])
async def update_question(
    request: Request,
    question_id: str,
    payload: QuestionUpdate,
) -> QuestionRead:
    """Partially update a question by id."""

    try:
        await ensure_beanie_initialized(request.app.state.mongo_client)
        q = await get_or_404(Question, question_id, "Question")

        update_data = payload.model_dump(exclude_unset=True)
        options = payload.options if payload.options is not None else q.options
        correct = (
            payload.correct_option_indices
            if payload.correct_option_indices is not None
            else q.correct_option_indices
        )
        try:
            validate_correct_indices(options, correct)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        for k, v in update_data.items():
            setattr(q, k, v)

        await q.save()
    except ServerSelectionTimeoutError as exc:
        raise HTTPException(status_code=503, detail="MongoDB is unavailable.") from exc

    return _serialize_question(q)


@router.delete("/questions/{question_id}", response_model=DeletedResponse, dependencies=[Depends(require_admin)])
async def delete_question(request: Request, question_id: str) -> DeletedResponse:
    """Delete one question by id."""

    if not PydanticObjectId.is_valid(question_id):
        raise HTTPException(status_code=404, detail="Question not found")

    try:
        await ensure_beanie_initialized(request.app.state.mongo_client)
        result = await Question.get_motor_collection().delete_one({"_id": PydanticObjectId(question_id)})
    except ServerSelectionTimeoutError as exc:
        raise HTTPException(status_code=503, detail="MongoDB is unavailable.") from exc

    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Question not found")

    return DeletedResponse(deleted_id=question_id)


@router.get("/taxonomy", response_model=TaxonomyResponse, dependencies=[Depends(require_admin)])
async def get_taxonomy() -> TaxonomyResponse:
    """Admin: every topic/subtopic used by questions (incl. drafts) or notes, with counts."""

    return TaxonomyResponse(topics=await taxonomy())


@router.put("/topics/{topic}/rename", response_model=RenameResponse, dependencies=[Depends(require_admin)])
async def rename_topic(topic: str, body: TopicRenameRequest) -> RenameResponse:
    """Rename a topic on every question, note and generation job."""

    return RenameResponse(**await rename({"topic": topic}, "topic", body.new_topic, "topic"))


@router.put(
    "/topics/{topic}/subtopics/{subtopic}/rename",
    response_model=RenameResponse,
    dependencies=[Depends(require_admin)],
)
async def rename_subtopic(topic: str, subtopic: str, body: SubtopicRenameRequest) -> RenameResponse:
    """Rename a subtopic within a topic on every question, note and generation job."""

    return RenameResponse(
        **await rename({"topic": topic, "subtopic": subtopic}, "subtopic", body.new_subtopic, "subtopic")
    )
