from __future__ import annotations

import re

from material_platform.domain.research_material import ContentUnit
from material_platform.extraction.window import token_count

_SECTION = re.compile(
    r"^(#{1,6}\s|chapter\s+\d|section\s+\d)",
    re.IGNORECASE,
)


def group_units(
    units: tuple[ContentUnit, ...],
    *,
    target_tokens: int,
) -> tuple[tuple[ContentUnit, ...], ...]:
    """Pack consecutive units into analysis groups. Does not use CHUNK_TOKENS."""
    target = max(target_tokens, 1)
    flush_at = max(int(target * 0.6), 1)
    groups: list[tuple[ContentUnit, ...]] = []
    current: list[ContentUnit] = []
    used = 0
    for unit in units:
        size = max(token_count(unit.content), 1)
        at_boundary = _section_start(unit)
        if current and (used + size > target or (used >= flush_at and at_boundary)):
            groups.append(tuple(current))
            current = [unit]
            used = size
            continue
        current.append(unit)
        used += size
    if current:
        groups.append(tuple(current))
    return tuple(groups)


def content_tokens(units: tuple[ContentUnit, ...]) -> int:
    return sum(token_count(unit.content) for unit in units)


def _section_start(unit: ContentUnit) -> bool:
    if unit.location.section:
        return True
    first = unit.content.lstrip().splitlines()[:1]
    return bool(first and _SECTION.match(first[0]))
