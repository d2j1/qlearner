"""Admin endpoints for versioned prompt templates."""

from fastapi import APIRouter, Depends

from app.auth import require_admin
from app.models.prompt_template import PromptTemplate
from app.routes.common import get_or_404
from app.schemas.generation_schema import PromptPlaceholders, PromptTemplateCreate, PromptTemplateRead

router = APIRouter(prefix="/api/prompts", tags=["prompts"], dependencies=[Depends(require_admin)])

PLACEHOLDERS = {
    "topic": "Job topic",
    "subtopic": "Job subtopic",
    "count": "Number of questions for this call",
    "difficulty": "Requested difficulty, e.g. 'a mix of EASY, MEDIUM and HARD'",
    "focus": "Free-text focus description, or '(the whole subtopic)'",
    "notes": "Selected notes (titles + markdown), or '(none)'",
    "knowledge_rule": "Whether facts outside the notes are allowed",
    "extra_instructions": "Per-run extra instructions, or '(none)'",
    "schema": "JSON schema the reply must match (keep this in every template)",
}


def _read(t: PromptTemplate) -> PromptTemplateRead:
    return PromptTemplateRead(id=str(t.id), **t.model_dump(exclude={"id", "revision_id"}))


async def _make_default(template: PromptTemplate) -> None:
    await PromptTemplate.get_motor_collection().update_many(
        {"_id": {"$ne": template.id}, "is_default": True}, {"$set": {"is_default": False}}
    )
    if not template.is_default:
        template.is_default = True
        await template.save()


@router.get("/placeholders", response_model=PromptPlaceholders)
async def list_placeholders() -> PromptPlaceholders:
    return PromptPlaceholders(placeholders=PLACEHOLDERS)


@router.get("", response_model=list[PromptTemplateRead])
async def list_templates(all_versions: bool = False) -> list[PromptTemplateRead]:
    """Latest version of each template (or every version with all_versions=true)."""

    templates = await PromptTemplate.find_all().sort([("name", 1), ("version", -1)]).to_list()
    if not all_versions:
        latest: dict[str, PromptTemplate] = {}
        for t in templates:
            latest.setdefault(t.name, t)
        # keep the default visible even when it is an older version
        templates = list(latest.values()) + [t for t in templates if t.is_default and latest[t.name] is not t]
    return [_read(t) for t in templates]


@router.get("/{template_id}", response_model=PromptTemplateRead)
async def get_template(template_id: str) -> PromptTemplateRead:
    return _read(await get_or_404(PromptTemplate, template_id, "Prompt template"))


@router.post("", response_model=PromptTemplateRead, status_code=201)
async def create_template(body: PromptTemplateCreate) -> PromptTemplateRead:
    latest = await PromptTemplate.find(PromptTemplate.name == body.name).sort("-version").first_or_none()
    template = PromptTemplate(**body.model_dump(), version=(latest.version + 1) if latest else 1)
    await template.insert()
    if template.is_default:
        await _make_default(template)
    return _read(template)


@router.post("/{template_id}/default", response_model=PromptTemplateRead)
async def set_default(template_id: str) -> PromptTemplateRead:
    template = await get_or_404(PromptTemplate, template_id, "Prompt template")
    await _make_default(template)
    return _read(template)
