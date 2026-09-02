from __future__ import annotations

import re

from material_platform.domain.research_material import ContentUnit

_WORD = re.compile(r"[A-Za-z][A-Za-z0-9_.-]{2,}")
_HEADING = re.compile(r"^#{1,6}\s+(.+)$", re.MULTILINE)
_STOP = frozenset(
    {
        "this",
        "that",
        "with",
        "from",
        "into",
        "return",
        "none",
        "true",
        "false",
        "self",
        "print",
        "the",
        "and",
        "for",
        "are",
    }
)


def unique(items: list[str], *, limit: int) -> tuple[str, ...]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        key = item.strip()
        if not key:
            continue
        lowered = key.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        out.append(key)
        if len(out) >= limit:
            break
    return tuple(out)


def from_text(text: str, *, limit: int = 40) -> tuple[str, ...]:
    words: list[str] = []
    words.extend(match.strip() for match in _HEADING.findall(text))
    for match in _WORD.findall(text):
        lowered = match.lower()
        if lowered in _STOP:
            continue
        words.append(match)
    return unique(words, limit=limit)


def from_units(units: tuple[ContentUnit, ...], *, limit: int = 80) -> tuple[str, ...]:
    words: list[str] = []
    for unit in units:
        for key in ("package", "title", "language", "summary"):
            value = unit.metadata.get(key)
            if isinstance(value, str) and value.strip():
                words.append(value.strip())
                words.extend(from_text(value, limit=20))
        for key in ("dependencies", "modules", "columns", "keywords", "entry_points"):
            value = unit.metadata.get(key)
            if isinstance(value, list):
                words.extend(str(item) for item in value if item)
        words.extend(from_text(unit.content, limit=40))
    return unique(words, limit=limit)


def grounded(
    requested: object,
    pool: tuple[str, ...],
    *,
    limit: int,
) -> tuple[str, ...]:
    allowed = {item.lower(): item for item in pool}
    picked: list[str] = []
    if isinstance(requested, list):
        for item in requested:
            if not isinstance(item, str) or not item.strip():
                continue
            match = allowed.get(item.strip().lower())
            if match is None:
                continue
            picked.append(match)
    if len(picked) >= limit:
        return unique(picked, limit=limit)
    picked.extend(pool)
    return unique(picked, limit=limit)
