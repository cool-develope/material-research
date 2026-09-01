from __future__ import annotations

from collections.abc import Iterator
from io import BytesIO
from typing import Any

from docx import Document
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph

from material_platform.domain.research_material import ContentUnit
from material_platform.extraction.common import (
    MaterialFile,
    line_count,
    make_unit,
    merge_unit_metadata,
)

_HEADINGS = frozenset({"heading 1", "heading 2", "heading1", "heading2"})


def extract_docx(item: MaterialFile) -> tuple[ContentUnit, ...]:
    try:
        document = Document(BytesIO(item.data))
    except Exception:
        return (_empty(item.path),)
    grouped = _group(_blocks(document))
    return merge_unit_metadata(_units(item.path, grouped), _core_meta(document))


def _core_meta(document: Any) -> dict[str, object]:
    try:
        props = document.core_properties
    except Exception:
        return {}
    fields: dict[str, object] = {}
    title = (props.title or "").strip()
    author = (props.author or "").strip()
    if title:
        fields["title"] = title
    if author:
        fields["author"] = author
    return fields


def _empty(path: str) -> ContentUnit:
    return make_unit(
        path=path,
        content="",
        unit_type="text",
        line_start=1,
        line_end=1,
    )


def _blocks(document: Any) -> Iterator[str | tuple[str, str]]:
    for child in document.element.body:
        if child.tag == qn("w:p"):
            paragraph = Paragraph(child, document)
            heading = _heading(paragraph)
            text = paragraph.text.strip()
            if heading:
                yield ("heading", heading)
            elif text:
                yield text
        elif child.tag == qn("w:tbl"):
            grid = _table(Table(child, document))
            if grid:
                yield grid


def _heading(paragraph: Paragraph) -> str | None:
    style = paragraph.style
    name = (style.name if style is not None else "") or ""
    if name.lower() not in _HEADINGS:
        return None
    title = paragraph.text.strip()
    return title or None


def _table(table: Table) -> str:
    rows = [
        "\t".join(cell.text.strip().replace("\n", " ") for cell in row.cells)
        for row in table.rows
    ]
    return "\n".join(row for row in rows if row.strip())


def _group(
    blocks: Iterator[str | tuple[str, str]],
) -> list[tuple[str | None, list[str]]]:
    sections: list[tuple[str | None, list[str]]] = []
    heading: str | None = None
    lines: list[str] = []

    def flush() -> None:
        nonlocal heading, lines
        if heading is not None or lines:
            sections.append((heading, lines))
        heading = None
        lines = []

    for block in blocks:
        if isinstance(block, tuple):
            flush()
            heading = block[1]
            lines = [block[1]]
        else:
            lines.append(block)
    flush()
    return sections or [(None, [])]


def _units(
    path: str, grouped: list[tuple[str | None, list[str]]]
) -> tuple[ContentUnit, ...]:
    cursor = 1
    units: list[ContentUnit] = []
    for heading, lines in grouped:
        content = "\n".join(lines)
        if not content:
            continue
        end = cursor + line_count(content) - 1
        units.append(
            make_unit(
                path=path,
                content=content,
                unit_type="section" if heading else "text",
                line_start=cursor,
                line_end=end,
                section=heading,
            )
        )
        cursor = end + 1
    if not units:
        return (_empty(path),)
    return tuple(units)
