"""Helpers for pulling a JSON object out of LLM output."""

import re

# Only a fence wrapping the whole reply. Fences *inside* JSON strings (code in
# question text) must be left alone.
_OUTER_FENCE = re.compile(r"^```[a-zA-Z]*\s*\n?(.*?)\n?```\s*$", re.DOTALL)


def extract_json(text: str) -> str:
    """Return the JSON object in `text`, tolerating an outer markdown fence and chatter around it."""

    text = text.strip()
    if text.startswith("{") or text.startswith("["):
        return text
    fenced = _OUTER_FENCE.match(text)
    if fenced:
        return fenced.group(1).strip()
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        return text[start : end + 1]
    return text
