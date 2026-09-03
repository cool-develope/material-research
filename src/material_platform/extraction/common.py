from __future__ import annotations

import hashlib

from material_platform.domain.research_material import (
    ContentLocation,
    ContentUnit,
    MaterialFile,
)

DEFAULT_MAX_UNITS = 20

__all__ = [
    "DEFAULT_MAX_UNITS",
    "MaterialFile",
    "decode_text",
    "line_count",
    "make_unit",
    "merge_unit_metadata",
    "unit_digest",
]


def unit_digest(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()


def decode_text(data: bytes) -> str:
    return data.decode("utf-8", errors="replace")


def line_count(text: str) -> int:
    if not text:
        return 1
    return max(len(text.splitlines()), 1)


def merge_unit_metadata(
    units: tuple[ContentUnit, ...], extra: dict[str, object]
) -> tuple[ContentUnit, ...]:
    if not extra:
        return units
    return tuple(
        unit.model_copy(update={"metadata": {**unit.metadata, **extra}})
        for unit in units
    )


def make_unit(
    *,
    path: str,
    content: str,
    unit_type: str,
    page: int | None = None,
    line_start: int | None = None,
    line_end: int | None = None,
    section: str | None = None,
    metadata: dict[str, object] | None = None,
    chunk_key: str | None = None,
) -> ContentUnit:
    if page is not None:
        unit_id = f"{path}:page:{page}"
    elif line_start is not None and line_end is not None:
        unit_id = f"{path}:lines:{line_start}-{line_end}"
    else:
        unit_id = path
    if chunk_key:
        unit_id = f"{unit_id}:{chunk_key}"
    return ContentUnit(
        unit_id=unit_id,
        type=unit_type,
        content=content,
        location=ContentLocation(
            path=path,
            page=page,
            line_start=line_start,
            line_end=line_end,
            section=section,
        ),
        digest=unit_digest(content),
        metadata=metadata or {},
    )
