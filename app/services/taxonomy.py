"""Topic/subtopic listing and renaming across every collection that stores them."""

from __future__ import annotations

from collections import defaultdict

from fastapi import HTTPException

from app.models.generation_job import GenerationJob
from app.models.note import Note
from app.models.question import Question


def _collections():
    return (
        Question.get_motor_collection(),
        Note.get_motor_collection(),
        GenerationJob.get_motor_collection(),
    )


async def _count_matches(match: dict) -> int:
    questions, notes, _jobs = _collections()
    return await questions.count_documents(match) + await notes.count_documents(match)


async def rename(match: dict, field: str, new_value: str, label: str) -> dict:
    """Set `field` to `new_value` on every question, note and job matching `match`.

    Raises 404 when nothing uses the old name and 422 when the name is unchanged.
    Returns per-collection counts plus whether the new name already existed (merge).
    """

    if match[field] == new_value:
        raise HTTPException(status_code=422, detail=f"The new {label} name is the same as the current one.")
    if not await _count_matches(match):
        raise HTTPException(status_code=404, detail=f"{label.capitalize()} not found")

    merged = bool(await _count_matches({**match, field: new_value}))
    questions, notes, jobs = _collections()
    update = {"$set": {field: new_value}}
    q = await questions.update_many(match, update)
    n = await notes.update_many(match, update)
    j = await jobs.update_many(match, update)
    return {
        "modified_count": int(q.modified_count),
        "notes_modified": int(n.modified_count),
        "jobs_modified": int(j.modified_count),
        "merged": merged,
    }


async def taxonomy() -> list[dict]:
    """Every topic and subtopic used by a question (any status but rejected) or a note, with counts."""

    questions, notes, _jobs = _collections()
    counts: dict[tuple[str, str], dict[str, int]] = defaultdict(lambda: {"question_count": 0, "draft_count": 0, "note_count": 0})

    rows = await questions.aggregate([
        {"$match": {"status": {"$ne": "rejected"}}},
        {"$group": {"_id": {"t": "$topic", "s": "$subtopic", "draft": {"$eq": ["$status", "draft"]}}, "n": {"$sum": 1}}},
    ]).to_list(length=None)
    for row in rows:
        key = (row["_id"]["t"], row["_id"]["s"])
        counts[key]["draft_count" if row["_id"]["draft"] else "question_count"] += row["n"]

    rows = await notes.aggregate([
        {"$group": {"_id": {"t": "$topic", "s": "$subtopic"}, "n": {"$sum": 1}}},
    ]).to_list(length=None)
    for row in rows:
        counts[(row["_id"]["t"], row["_id"]["s"])]["note_count"] += row["n"]

    topics: dict[str, dict] = {}
    for (topic, subtopic), c in sorted(counts.items(), key=lambda kv: (kv[0][0].lower(), kv[0][1].lower())):
        if not topic or not subtopic:
            continue
        entry = topics.setdefault(topic, {"topic": topic, "question_count": 0, "draft_count": 0, "note_count": 0, "subtopics": []})
        entry["subtopics"].append({"subtopic": subtopic, **c})
        for k, v in c.items():
            entry[k] += v
    return list(topics.values())
