"""Question and topic endpoints for the MCQ backend."""

from collections import defaultdict

from fastapi import APIRouter, HTTPException, Query, Request
from pymongo.errors import ServerSelectionTimeoutError

from app.database import ensure_beanie_initialized
from app.models.question import Question
from app.schemas.question_schema import (
    BulkQuestionResponse,
    ModifiedCountResponse,
    QuestionCreate,
    QuestionListResponse,
    QuestionRead,
    QuestionUpdate,
    SubtopicGroup,
    SubtopicRenameRequest,
    TopicListResponse,
    TopicQuestionsResponse,
    TopicRenameRequest,
)

router = APIRouter(prefix="/api", tags=["questions"])


def _serialize_question(question: Question) -> QuestionRead:
    """Convert a Beanie document into the API response schema."""

    return QuestionRead(
        id=str(question.id) if question.id else None,
        topic=question.topic,
        subtopic=question.subtopic,
        question_text=question.question_text,
        options=question.options,
        correct_option_indices=question.correct_option_indices,
        explanation=question.explanation,
        difficulty=question.difficulty,
        created_at=question.created_at,
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
        topics = await Question.get_motor_collection().distinct("topic")
    except ServerSelectionTimeoutError as exc:
        raise HTTPException(status_code=503, detail="MongoDB is unavailable.") from exc

    return TopicListResponse(topics=sorted(topic for topic in topics if topic))


@router.get("/questions", response_model=QuestionListResponse)
async def list_questions(
    request: Request,
    topic: str | None = Query(default=None),
    subtopic: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> QuestionListResponse:
    """Return a flat list of questions, optionally filtered by topic/subtopic."""

    try:
        await ensure_beanie_initialized(request.app.state.mongo_client)
        query: dict[str, str] = {}
        if topic is not None:
            query["topic"] = topic
        if subtopic is not None:
            query["subtopic"] = subtopic
        total, docs = await _count_and_load_questions(query, limit, offset)
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
        total, docs = await _count_and_load_questions({"topic": topic}, limit, offset)
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
        question = await Question.get(question_id)
    except ServerSelectionTimeoutError as exc:
        raise HTTPException(status_code=503, detail="MongoDB is unavailable.") from exc

    if question is None:
        raise HTTPException(status_code=404, detail="Question not found")

    return _serialize_question(question)


@router.post("/questions/bulk", response_model=BulkQuestionResponse, status_code=201)
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


@router.patch("/questions/{question_id}", response_model=QuestionRead)
async def update_question(
    request: Request,
    question_id: str,
    payload: QuestionUpdate,
) -> QuestionRead:
    """Partially update a question by id."""

    try:
        await ensure_beanie_initialized(request.app.state.mongo_client)
        q = await Question.get(question_id)
        if q is None:
            raise HTTPException(status_code=404, detail="Question not found")

        update_data = payload.model_dump(exclude_unset=True)
        for k, v in update_data.items():
            setattr(q, k, v)

        await q.save()
    except ServerSelectionTimeoutError as exc:
        raise HTTPException(status_code=503, detail="MongoDB is unavailable.") from exc

    return _serialize_question(q)


@router.put("/topics/{topic}/rename", response_model=ModifiedCountResponse)
async def rename_topic(topic: str, body: TopicRenameRequest, request: Request) -> ModifiedCountResponse:
    """Rename a topic across all questions."""

    try:
        await ensure_beanie_initialized(request.app.state.mongo_client)
        result = await Question.get_motor_collection().update_many(
            {"topic": topic}, {"$set": {"topic": body.new_topic}}
        )
    except ServerSelectionTimeoutError as exc:
        raise HTTPException(status_code=503, detail="MongoDB is unavailable.") from exc

    return ModifiedCountResponse(modified_count=int(result.modified_count))


@router.put(
    "/topics/{topic}/subtopics/{subtopic}/rename",
    response_model=ModifiedCountResponse,
)
async def rename_subtopic(
    topic: str,
    subtopic: str,
    body: SubtopicRenameRequest,
    request: Request,
) -> ModifiedCountResponse:
    """Rename a subtopic within a topic across all matching questions."""

    try:
        await ensure_beanie_initialized(request.app.state.mongo_client)
        result = await Question.get_motor_collection().update_many(
            {"topic": topic, "subtopic": subtopic}, {"$set": {"subtopic": body.new_subtopic}}
        )
    except ServerSelectionTimeoutError as exc:
        raise HTTPException(status_code=503, detail="MongoDB is unavailable.") from exc

    return ModifiedCountResponse(modified_count=int(result.modified_count))
