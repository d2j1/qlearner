"""Small helpers shared by the admin routers."""

from typing import TypeVar

from beanie import Document, PydanticObjectId
from fastapi import HTTPException

D = TypeVar("D", bound=Document)


async def get_or_404(model: type[D], doc_id: str, label: str) -> D:
    doc = await model.get(doc_id) if PydanticObjectId.is_valid(doc_id) else None
    if doc is None:
        raise HTTPException(status_code=404, detail=f"{label} not found")
    return doc


def parse_object_ids(ids: list[str], label: str) -> list[PydanticObjectId]:
    invalid = [i for i in ids if not PydanticObjectId.is_valid(i)]
    if invalid:
        raise HTTPException(status_code=422, detail=f"Invalid {label} id(s): {', '.join(invalid[:5])}")
    return [PydanticObjectId(i) for i in ids]
