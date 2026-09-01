from __future__ import annotations

import re

from material_platform.domain.research_material import ContentUnit
from material_platform.extraction.common import (
    MaterialFile,
    decode_text,
    line_count,
    make_unit,
)

_MD_H1 = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)


def extract_text(item: MaterialFile) -> ContentUnit:
    text = decode_text(item.data)
    end = line_count(text)
    extra: dict[str, object] = {}
    if item.suffix in {".md", ".markdown"}:
        match = _MD_H1.search(text)
        if match:
            extra["title"] = match.group(1).strip()
    return make_unit(
        path=item.path,
        content=text,
        unit_type="text",
        line_start=1,
        line_end=end,
        metadata=extra,
    )
