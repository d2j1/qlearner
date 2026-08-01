"""Request and response schemas for MCQ questions."""

from datetime import datetime
from typing import List, Optional

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator


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
    correct_option_indices: List[int] = Field(
        validation_alias=AliasChoices("correct_option_indices", "correct_option_index")
    )
    explanation: str
    difficulty: Optional[str] = "MEDIUM"

    @field_validator("correct_option_indices", mode="before")
    @classmethod
    def normalize_correct_option_indices(cls, value):
        if value is None:
            return value
        if isinstance(value, int):
            return [value]
        return value


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


class ModifiedCountResponse(BaseModel):
    """Response returned by rename operations."""

    modified_count: int


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


class TopicQuestionsResponse(BaseModel):
    """Frontend-friendly response for all questions under one topic."""

    topic: str
    total: int
    limit: int
    offset: int
    groups: List[SubtopicGroup]


class QuestionListResponse(BaseModel):
    """Frontend-friendly flat question list."""

    total: int
    limit: int
    offset: int
    items: List[QuestionRead]


class QuestionUpdate(BaseModel):
    """Partial update payload for a question."""

    subtopic: Optional[str] = None
    question_text: Optional[str] = None
    options: Optional[List[OptionSchema]] = None
    correct_option_indices: Optional[List[int]] = Field(
        default=None,
        validation_alias=AliasChoices("correct_option_indices", "correct_option_index"),
    )
    explanation: Optional[str] = None
    difficulty: Optional[str] = None

    @field_validator("correct_option_indices", mode="before")
    @classmethod
    def normalize_correct_option_indices(cls, value):
        if value is None:
            return value
        if isinstance(value, int):
            return [value]
        return value


class TopicRenameRequest(BaseModel):
    new_topic: str


class SubtopicRenameRequest(BaseModel):
    new_subtopic: str
