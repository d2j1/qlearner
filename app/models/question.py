"""Beanie document model for multiple-choice questions."""

from datetime import UTC, datetime
from typing import List

from beanie import Document, Indexed
from pydantic import BaseModel, Field


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
    correct_option_indices: List[int]
    explanation: str
    difficulty: str = "MEDIUM"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    class Settings:
        """Beanie collection configuration."""

        name = "mcq_questions"
        # Topic and subtopic lookups are primary access patterns for the API.
        indexes = ["topic", "subtopic"]
