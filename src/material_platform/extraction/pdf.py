from __future__ import annotations

from io import BytesIO

from pypdf import PdfReader

from material_platform.domain.research_material import ContentUnit
from material_platform.extraction.common import MaterialFile, make_unit


def extract_pdf(item: MaterialFile) -> tuple[ContentUnit, ...]:
    reader = PdfReader(BytesIO(item.data))
    units: list[ContentUnit] = []
    for index, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        units.append(
            make_unit(
                path=item.path,
                content=text,
                unit_type="page",
                page=index,
            )
        )
    if not units:
        units.append(
            make_unit(
                path=item.path,
                content="",
                unit_type="page",
                page=1,
            )
        )
    return tuple(units)
