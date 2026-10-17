"""Admin CRUD for study notes."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query

from app.auth import require_admin
from app.models.note import Note
from app.routes.common import get_or_404
from app.schemas.generation_schema import NoteCreate, NoteListResponse, NoteRead, NoteSummary, NoteUpdate
from app.schemas.question_schema import DeletedResponse

router = APIRouter(prefix="/api/notes", tags=["notes"], dependencies=[Depends(require_admin)])


def _read(note: Note) -> NoteRead:
    return NoteRead(id=str(note.id), **note.model_dump(exclude={"id", "revision_id"}))


def _summary(note: Note) -> NoteSummary:
    return NoteSummary(
        id=str(note.id),
        topic=note.topic,
        subtopic=note.subtopic,
        title=note.title,
        preview=note.content[:200],
        content_length=len(note.content),
        tags=note.tags,
        created_at=note.created_at,
        updated_at=note.updated_at,
    )


@router.get("", response_model=NoteListResponse)
async def list_notes(
    topic: str | None = None,
    subtopic: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> NoteListResponse:
    query: dict = {}
    if topic is not None:
        query["topic"] = topic
    if subtopic is not None:
        query["subtopic"] = subtopic
    total = await Note.get_motor_collection().count_documents(query)
    notes = await Note.find(query).sort("-updated_at").skip(offset).limit(limit).to_list()
    return NoteListResponse(total=total, limit=limit, offset=offset, items=[_summary(n) for n in notes])


@router.post("", response_model=NoteRead, status_code=201)
async def create_note(body: NoteCreate) -> NoteRead:
    note = Note(**body.model_dump())
    await note.insert()
    return _read(note)


@router.get("/{note_id}", response_model=NoteRead)
async def get_note(note_id: str) -> NoteRead:
    return _read(await get_or_404(Note, note_id, "Note"))


@router.patch("/{note_id}", response_model=NoteRead)
async def update_note(note_id: str, body: NoteUpdate) -> NoteRead:
    note = await get_or_404(Note, note_id, "Note")
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(note, key, value)
    note.updated_at = datetime.now(UTC)
    await note.save()
    return _read(note)


@router.delete("/{note_id}", response_model=DeletedResponse)
async def delete_note(note_id: str) -> DeletedResponse:
    note = await get_or_404(Note, note_id, "Note")
    await note.delete()
    return DeletedResponse(deleted_id=note_id)
