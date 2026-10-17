"""Beanie document model for versioned prompt templates.

Templates are immutable: editing one creates a new document with the same
name and the next version number, so every generation job can point at the
exact prompt it used.
"""

from datetime import UTC, datetime

from beanie import Document
from pydantic import Field


class PromptTemplate(Document):
    name: str
    version: int = 1
    system_prompt: str
    user_prompt: str
    is_default: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    class Settings:
        name = "prompt_templates"
        indexes = ["name"]
