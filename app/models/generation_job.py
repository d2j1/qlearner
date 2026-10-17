"""Beanie document model recording every generation run."""

from datetime import UTC, datetime
from typing import List, Literal, Optional

from beanie import Document, PydanticObjectId
from pydantic import BaseModel, Field

JobStatus = Literal["queued", "running", "succeeded", "failed"]


class GenerationParams(BaseModel):
    count: int = 10
    difficulty: Literal["MIXED", "EASY", "MEDIUM", "HARD"] = "MIXED"
    allow_outside_knowledge: bool = False


class GenerationJob(Document):
    topic: str
    subtopic: str
    note_ids: List[PydanticObjectId] = Field(default_factory=list)
    focus: Optional[str] = None  # free-text topic description used with or instead of notes
    extra_instructions: Optional[str] = None
    params: GenerationParams = Field(default_factory=GenerationParams)
    llm_config_id: PydanticObjectId
    llm_model: str
    prompt_template_id: PydanticObjectId
    prompt_template_version: int
    status: JobStatus = "queued"
    created_question_ids: List[PydanticObjectId] = Field(default_factory=list)
    duplicates_skipped: int = 0
    error: Optional[str] = None
    raw_output: Optional[str] = None  # kept only on failure, truncated
    input_tokens: int = 0
    output_tokens: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None

    class Settings:
        name = "generation_jobs"
        indexes = ["status", "created_at"]
