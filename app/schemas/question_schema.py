"""Request and response schemas for MCQ questions."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class OptionSchema(BaseModel):
    """Schema for one option in an MCQ payload."""

    index: int
    text: str


class QuestionBase(BaseModel):
    """Shared fields across create, read, and generator payloads."""

    topic: str
    subtopic: str
    question_text: str
    options: List[OptionSchema]
    # support multiple correct options
    correct_option_indices: List[int]
    explanation: str
    difficulty: Optional[str] = "MEDIUM"


class QuestionCreate(QuestionBase):
    """Payload accepted by the bulk ingest endpoint."""


class QuestionRead(QuestionBase):
    """Payload returned by the question listing endpoint."""

    id: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BulkQuestionResponse(BaseModel):
    """Standard response for bulk inserts."""

    inserted_count: int
    inserted_ids: List[str] = Field(default_factory=list)


class TopicListResponse(BaseModel):
    """Response wrapper for the topic listing endpoint."""

    topics: List[str]


class GeneratedQuestionBatch(BaseModel):
    """Strict wrapper used by the generator script for LLM output."""

    questions: List[QuestionCreate]


class SubtopicGroup(BaseModel):
    """Grouping of questions under a subtopic for a topic-level query."""

    subtopic: str
    questions: List[QuestionRead]
