"""Beanie document model for application users."""

from datetime import UTC, datetime

from beanie import Document, Indexed
from pydantic import Field


class User(Document):
    """Persisted user stored in the users collection.

    `role` is either "user" (can practice) or "admin" (can manage questions).
    """

    email: Indexed(str, unique=True)
    name: str
    password_hash: str
    role: str = "user"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    class Settings:
        """Beanie collection configuration."""

        name = "users"
