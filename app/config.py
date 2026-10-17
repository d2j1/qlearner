"""Application settings for the MCQ backend.

The project keeps configuration small and explicit so it can be deployed with
environment variables only. The MongoDB URI defaults to a local database so the
service can start in development without any extra setup.
"""

from functools import lru_cache
from pydantic import AliasChoices, Field

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed runtime settings loaded from environment variables."""

    mongo_url: str = Field(
        default="mongodb://localhost:27017/mcq_db",
        validation_alias=AliasChoices("MONGO_URL", "MONGODB_URI", "MONGO_URI", "mongo_url"),
    )
    app_name: str = "MCQ Practice Backend"
    api_prefix: str = "/api"
    cors_allow_origins: str = Field(
        default="http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173,http://127.0.0.1:5173"
    )
    cors_allow_credentials: bool = False
    jwt_secret: str = "change-me-in-production"
    jwt_expire_minutes: int = 60 * 24 * 7
    # Comma-separated emails that get the admin role on register/login.
    admin_emails: str = ""

    @property
    def admin_email_list(self) -> set[str]:
        return {e.strip().lower() for e in self.admin_emails.split(",") if e.strip()}

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance for the whole process lifetime."""

    return Settings()
