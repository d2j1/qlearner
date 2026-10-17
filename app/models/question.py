"""Beanie document model for multiple-choice questions."""

from datetime import UTC, datetime
from typing import List, Literal, Optional

from beanie import Document, Indexed, PydanticObjectId
from pydantic import AliasChoices, BaseModel, Field, field_validator


class Option(BaseModel):
    """A single answer option in an MCQ."""

    index: int
    text: str


class Question(Document):
    """Persisted MCQ document stored in the mcq_questions collection.

    Fields changed to support grouping by subtopic and multiple correct answers:
    - `subtopic`: string grouping within a topic
    - `correct_option_indices`: list of integers indicating all correct options
    """

    topic: Indexed(str)
    subtopic: str
    question_text: str
    options: List[Option]
    correct_option_indices: List[int] = Field(
        validation_alias=AliasChoices("correct_option_indices", "correct_option_index")
    )
    explanation: str
    difficulty: str = "MEDIUM"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    # Generated questions start as drafts; documents without a status predate
    # this field and are treated as approved.
    status: Literal["draft", "approved", "rejected"] = "approved"
    source_note_ids: List[PydanticObjectId] = Field(default_factory=list)
    generation_job_id: Optional[PydanticObjectId] = None
    tags: List[str] = Field(default_factory=list)

    @field_validator("correct_option_indices", mode="before")
    @classmethod
    def normalize_correct_option_indices(cls, value):
        if value is None:
            return value
        if isinstance(value, int):
            return [value]
        return value

    class Settings:
        """Beanie collection configuration."""

        name = "mcq_questions"
        # Topic and subtopic lookups are primary access patterns for the API.
        indexes = ["topic", "subtopic", "status", "generation_job_id"]


# Mongo filter matching questions visible in practice: approved (or legacy without a
# status) and with a usable topic/subtopic. Malformed legacy documents are excluded
# so they cannot crash listings that load them into the Question model.
VISIBLE_FILTER = {
    "status": {"$nin": ["draft", "rejected"]},
    "topic": {"$type": "string", "$ne": ""},
    "subtopic": {"$type": "string", "$ne": ""},
}
