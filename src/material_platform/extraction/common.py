from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from material_platform.domain.research_material import (
    ContentLocation,
    ContentUnit,
)


@dataclass(frozen=True)
class MaterialFile:
    path: str
    data: bytes

    @property
    def suffix(self) -> str:
        return Path(self.path).suffix.lower()


def unit_digest(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()


def decode_text(data: bytes) -> str:
    return data.decode("utf-8", errors="replace")


def line_count(text: str) -> int:
    if not text:
        return 1
    return max(len(text.splitlines()), 1)


def make_unit(
    *,
    path: str,
    content: str,
    unit_type: str,
    page: int | None = None,
    line_start: int | None = None,
    line_end: int | None = None,
    metadata: dict[str, object] | None = None,
) -> ContentUnit:
    if page is not None:
        unit_id = f"{path}:page:{page}"
    elif line_start is not None and line_end is not None:
        unit_id = f"{path}:lines:{line_start}-{line_end}"
    else:
        unit_id = path
    return ContentUnit(
        unit_id=unit_id,
        type=unit_type,
        content=content,
        location=ContentLocation(
            path=path,
            page=page,
            line_start=line_start,
            line_end=line_end,
        ),
        digest=unit_digest(content),
        metadata=metadata or {},
    )
