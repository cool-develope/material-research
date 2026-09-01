from __future__ import annotations

from io import BytesIO

from pypdf import PdfReader

from material_platform.domain.research_material import ContentUnit
from material_platform.extraction.common import (
    MaterialFile,
    make_unit,
    merge_unit_metadata,
)


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
    return merge_unit_metadata(tuple(units), _pdf_meta(reader))


def _pdf_meta(reader: PdfReader) -> dict[str, object]:
    fields: dict[str, object] = {"pages": len(reader.pages)}
    info = reader.metadata
    if info is None:
        return fields
    title = _clean(info.title)
    author = _clean(info.author) or _clean(getattr(info, "creator", None))
    if title:
        fields["title"] = title
    if author:
        fields["author"] = author
    return fields


def _clean(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
