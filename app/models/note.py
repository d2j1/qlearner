"""Beanie document model for study notes that questions are generated from."""

from datetime import UTC, datetime
from typing import List

from beanie import Document, Indexed
from pydantic import Field


class Note(Document):
    topic: Indexed(str)
    subtopic: str
    title: str
    content: str  # markdown
    tags: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    class Settings:
        name = "notes"
        indexes = ["topic", "subtopic"]
