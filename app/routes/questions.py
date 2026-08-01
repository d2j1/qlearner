"""Question and topic endpoints for the MCQ backend."""

from fastapi import APIRouter, HTTPException, Query, Request
from pymongo.errors import ServerSelectionTimeoutError
from collections import defaultdict

from app.database import ensure_beanie_initialized
from app.models.question import Question
from app.schemas.question_schema import (
    BulkQuestionResponse,
    QuestionCreate,
    QuestionRead,
    TopicListResponse,
    SubtopicGroup,
    QuestionUpdate,
    TopicRenameRequest,
    SubtopicRenameRequest,
)

router = APIRouter(prefix="/api", tags=["questions"])


def _serialize_question(question: Question) -> QuestionRead:
    """Convert a Beanie document into the API response schema."""

    return QuestionRead(
        id=str(question.id) if question.id else None,
        topic=question.topic,
        question_text=question.question_text,
        options=question.options,
        correct_option_index=question.correct_option_index,
        explanation=question.explanation,
        difficulty=question.difficulty,
        created_at=question.created_at,
    )


@router.get("/questions/{topic}", response_model=list[QuestionRead])
async def get_questions_by_topic(
    request: Request,
    topic: str,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> list[SubtopicGroup]:
    """Return questions for a topic grouped by subtopic.

    For the first iteration we fetch matching documents and group them in
    memory by `subtopic`. Pagination is applied at the document level.
    """

    try:
        await ensure_beanie_initialized(request.app.state.mongo_client)
        docs = (
            await Question.find(Question.topic == topic)
            .skip(offset)
            .limit(limit)
            .to_list()
        )
    except ServerSelectionTimeoutError as exc:
        raise HTTPException(status_code=503, detail="MongoDB is unavailable.") from exc

    groups: dict[str, list[QuestionRead]] = defaultdict(list)
    for doc in docs:
        q = _serialize_question(doc)
        groups[q.subtopic].append(q)

    return [SubtopicGroup(subtopic=sub, questions=qs) for sub, qs in groups.items()]


@router.get("/topics", response_model=TopicListResponse)
async def get_topics(request: Request) -> TopicListResponse:
    """Return the distinct set of stored topics."""

    try:
        await ensure_beanie_initialized(request.app.state.mongo_client)
        topics = await Question.get_motor_collection().distinct("topic")
    except ServerSelectionTimeoutError as exc:
        raise HTTPException(status_code=503, detail="MongoDB is unavailable.") from exc

    return TopicListResponse(topics=sorted(topic for topic in topics if topic))


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


@router.put("/topics/{topic}/rename")
async def rename_topic(topic: str, body: TopicRenameRequest, request: Request):
    """Rename a topic across all questions.

    This performs a bulk update setting `topic` to `new_topic` where the old
    topic matches. Returns the number of modified documents.
    """

    try:
        await ensure_beanie_initialized(request.app.state.mongo_client)
        result = await Question.get_motor_collection().update_many(
            {"topic": topic}, {"$set": {"topic": body.new_topic}}
        )
    except ServerSelectionTimeoutError as exc:
        raise HTTPException(status_code=503, detail="MongoDB is unavailable.") from exc

    return {"modified_count": int(result.modified_count)}


@router.put("/topics/{topic}/subtopics/{subtopic}/rename")
async def rename_subtopic(topic: str, subtopic: str, body: SubtopicRenameRequest, request: Request):
    """Rename a subtopic within a topic across all matching questions."""

    try:
        await ensure_beanie_initialized(request.app.state.mongo_client)
        result = await Question.get_motor_collection().update_many(
            {"topic": topic, "subtopic": subtopic}, {"$set": {"subtopic": body.new_subtopic}}
        )
    except ServerSelectionTimeoutError as exc:
        raise HTTPException(status_code=503, detail="MongoDB is unavailable.") from exc

    return {"modified_count": int(result.modified_count)}
