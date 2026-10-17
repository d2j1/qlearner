"""Request and response schemas for notes, prompt templates and generation jobs."""

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, model_validator

# ---------------------------------------------------------------- notes


class NoteCreate(BaseModel):
    topic: str = Field(min_length=1, max_length=200)
    subtopic: str = Field(min_length=1, max_length=200)
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=200_000)
    tags: List[str] = Field(default_factory=list)


class NoteUpdate(BaseModel):
    topic: Optional[str] = Field(default=None, min_length=1, max_length=200)
    subtopic: Optional[str] = Field(default=None, min_length=1, max_length=200)
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    content: Optional[str] = Field(default=None, min_length=1, max_length=200_000)
    tags: Optional[List[str]] = None


class NoteRead(BaseModel):
    id: str
    topic: str
    subtopic: str
    title: str
    content: str
    tags: List[str]
    created_at: datetime
    updated_at: datetime


class NoteSummary(BaseModel):
    """List view: content replaced by a short preview and its length."""

    id: str
    topic: str
    subtopic: str
    title: str
    preview: str
    content_length: int
    tags: List[str]
    created_at: datetime
    updated_at: datetime


class NoteListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: List[NoteSummary]


# ---------------------------------------------------------------- prompt templates


class PromptTemplateCreate(BaseModel):
    """Create a template; reusing an existing name creates its next version."""

    name: str = Field(min_length=1, max_length=100)
    system_prompt: str = Field(min_length=1, max_length=20_000)
    user_prompt: str = Field(min_length=1, max_length=50_000)
    is_default: bool = False


class PromptTemplateRead(BaseModel):
    id: str
    name: str
    version: int
    system_prompt: str
    user_prompt: str
    is_default: bool
    created_at: datetime


class PromptPlaceholders(BaseModel):
    placeholders: dict[str, str]


# ---------------------------------------------------------------- generation jobs

Difficulty = Literal["MIXED", "EASY", "MEDIUM", "HARD"]


class GenerationJobCreate(BaseModel):
    topic: str = Field(min_length=1, max_length=200)
    subtopic: str = Field(min_length=1, max_length=200)
    note_ids: List[str] = Field(default_factory=list, max_length=50)
    focus: Optional[str] = Field(default=None, max_length=2000)
    extra_instructions: Optional[str] = Field(default=None, max_length=4000)
    count: int = Field(default=10, ge=1, le=50)
    difficulty: Difficulty = "MIXED"
    allow_outside_knowledge: bool = False
    llm_config_id: Optional[str] = None  # default config when omitted
    prompt_template_id: Optional[str] = None  # default template when omitted

    @model_validator(mode="after")
    def needs_source(self):
        if not self.note_ids and not (self.focus and self.focus.strip()):
            raise ValueError("Provide note_ids, a focus description, or both.")
        return self


class GenerationJobRead(BaseModel):
    id: str
    topic: str
    subtopic: str
    note_ids: List[str]
    focus: Optional[str]
    extra_instructions: Optional[str]
    count: int
    difficulty: str
    allow_outside_knowledge: bool
    llm_config_id: str
    llm_model: str
    prompt_template_id: str
    prompt_template_version: int
    status: str
    created_question_ids: List[str]
    created_count: int
    duplicates_skipped: int
    error: Optional[str]
    raw_output: Optional[str]
    input_tokens: int
    output_tokens: int
    created_at: datetime
    started_at: Optional[datetime]
    finished_at: Optional[datetime]


class GenerationJobListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: List[GenerationJobRead]
