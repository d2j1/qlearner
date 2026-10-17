"""Request and response schemas for MCQ questions."""

from datetime import datetime
from typing import List, Optional

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator, model_validator


class OptionSchema(BaseModel):
    """Schema for one option in an MCQ payload."""

    index: int
    text: str


def validate_correct_indices(options: List[OptionSchema], correct_option_indices: List[int]) -> None:
    """Ensure option indices are unique and every correct index refers to an option."""

    option_indices = [option.index for option in options]
    if len(set(option_indices)) != len(option_indices):
        raise ValueError("Option indices must be unique.")
    if not correct_option_indices:
        raise ValueError("At least one correct option index is required.")
    if len(set(correct_option_indices)) != len(correct_option_indices):
        raise ValueError("correct_option_indices must not contain duplicates.")
    unknown = sorted(set(correct_option_indices) - set(option_indices))
    if unknown:
        raise ValueError(f"correct_option_indices {unknown} do not match any option index {sorted(option_indices)}.")


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

    @model_validator(mode="after")
    def check_correct_indices(self):
        validate_correct_indices(self.options, self.correct_option_indices)
        return self


class QuestionRead(QuestionBase):
    """Payload returned by the question listing endpoint."""

    id: Optional[str] = None
    created_at: datetime
    status: str = "approved"
    tags: List[str] = Field(default_factory=list)
    source_note_ids: List[str] = Field(default_factory=list)
    generation_job_id: Optional[str] = None

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
    tags: Optional[List[str]] = None

    @field_validator("correct_option_indices", mode="before")
    @classmethod
    def normalize_correct_option_indices(cls, value):
        if value is None:
            return value
        if isinstance(value, int):
            return [value]
        return value


class SubtopicSummary(BaseModel):
    """One subtopic within a topic and how many questions it holds."""

    subtopic: str
    question_count: int


class SubtopicListResponse(BaseModel):
    """Response wrapper for the subtopic listing endpoint."""

    topic: str
    subtopics: List[SubtopicSummary]


class DeletedResponse(BaseModel):
    """Response returned after deleting a question."""

    deleted_id: str


class TopicRenameRequest(BaseModel):
    new_topic: str = Field(min_length=1, max_length=200)

    @field_validator("new_topic", mode="before")
    @classmethod
    def strip(cls, value):
        return value.strip() if isinstance(value, str) else value


class SubtopicRenameRequest(BaseModel):
    new_subtopic: str = Field(min_length=1, max_length=200)

    @field_validator("new_subtopic", mode="before")
    @classmethod
    def strip(cls, value):
        return value.strip() if isinstance(value, str) else value


class RenameResponse(ModifiedCountResponse):
    """Rename result. `modified_count` counts questions (kept for older clients)."""

    notes_modified: int = 0
    jobs_modified: int = 0
    merged: bool = False  # the new name was already in use, so the two groups are now one


class SubtopicTaxonomy(BaseModel):
    subtopic: str
    question_count: int  # approved / visible in practice
    draft_count: int
    note_count: int


class TopicTaxonomy(BaseModel):
    topic: str
    question_count: int
    draft_count: int
    note_count: int
    subtopics: List[SubtopicTaxonomy]


class TaxonomyResponse(BaseModel):
    topics: List[TopicTaxonomy]


class IdsRequest(BaseModel):
    """A list of question ids for bulk draft actions."""

    ids: List[str] = Field(min_length=1, max_length=500)


class BulkStatusResponse(BaseModel):
    modified_count: int
