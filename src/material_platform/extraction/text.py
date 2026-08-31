from __future__ import annotations

from material_platform.domain.research_material import ContentUnit
from material_platform.extraction.common import (
    MaterialFile,
    decode_text,
    line_count,
    make_unit,
)


def extract_text(item: MaterialFile) -> ContentUnit:
    text = decode_text(item.data)
    end = line_count(text)
    return make_unit(
        path=item.path,
        content=text,
        unit_type="text",
        line_start=1,
        line_end=end,
    )
