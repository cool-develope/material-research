from __future__ import annotations

import re

from material_platform.classification.deterministic import ClassificationDecision
from material_platform.discovery.formats import ARTIFACT_FORMATS, BINARY_FORMATS
from material_platform.domain.enums import MaterialType
from material_platform.domain.research_material import ContentUnit
from material_platform.extraction.common import make_unit
from material_platform.extraction.symbol import split_symbols
from material_platform.extraction.window import (
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_CHUNK_TOKENS,
    token_count,
    window_spans,
    window_text,
)

_HEADING = re.compile(r"^(#{1,2})[ \t]+(.+?)\s*$")
_STUB_OFFICE = frozenset({"xlsx", "pptx", "doc"})


def chunk_units(
    decision: ClassificationDecision,
    units: tuple[ContentUnit, ...],
    *,
    chunk_tokens: int = DEFAULT_CHUNK_TOKENS,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> tuple[ContentUnit, ...]:
    if not units:
        return ()
    size = max(chunk_tokens, 1)
    overlap = chunk_overlap
    material_type = decision.material_type
    subtype = decision.subtype
    if subtype in ARTIFACT_FORMATS or subtype in BINARY_FORMATS:
        kind = "artifact" if subtype in ARTIFACT_FORMATS else "stub"
        chunks = _passthrough(units, kind)
    elif subtype in _STUB_OFFICE:
        chunks = _passthrough(units, "stub")
    elif material_type is MaterialType.DOCUMENT and subtype == "pdf":
        chunks = _fit_all(units, "document.pages", size=size, overlap=overlap)
    elif material_type is MaterialType.DOCUMENT and subtype in {"docx", "docm"}:
        chunks = _fit_all(
            units,
            "document.sections" if _headed(units) else "document.window",
            size=size,
            overlap=overlap,
        )
    elif material_type is MaterialType.DOCUMENT and subtype == "markdown":
        chunks = _markdown(units, size=size, overlap=overlap)
    elif material_type is MaterialType.DOCUMENT:
        chunks = _fit_all(units, "document.window", size=size, overlap=overlap)
    elif material_type is MaterialType.DATASET:
        chunks = _fit_all(units, "table", size=size, overlap=overlap)
    elif material_type in {MaterialType.PROJECT, MaterialType.CODE}:
        chunks = _code(units, size=size, overlap=overlap)
    else:
        chunks = _passthrough(units, "passthrough")
    return _number(chunks)


def _code(
    units: tuple[ContentUnit, ...], *, size: int, overlap: int
) -> list[ContentUnit]:
    chunks: list[ContentUnit] = []
    for unit in units:
        symbols = split_symbols(unit)
        if symbols:
            for piece in symbols:
                chunks.extend(
                    _fit_unit(
                        piece, strategy="code.symbol", size=size, overlap=overlap
                    )
                )
            continue
        chunks.extend(
            _fit_unit(unit, strategy="code.file", size=size, overlap=overlap)
        )
    return chunks


def _headed(units: tuple[ContentUnit, ...]) -> bool:
    return any(unit.location.section for unit in units)


def _markdown(
    units: tuple[ContentUnit, ...], *, size: int, overlap: int
) -> list[ContentUnit]:
    chunks: list[ContentUnit] = []
    for unit in units:
        sections = _split_markdown(unit.content)
        headed = any(heading for heading, _body, _start, _end in sections)
        strategy = "document.sections" if headed else "document.window"
        base = unit.location.line_start or 1
        path = unit.location.path or unit.unit_id
        for heading, body, start, end in sections:
            piece = make_unit(
                path=path,
                content=body,
                unit_type="section" if heading else unit.type,
                line_start=base + start - 1,
                line_end=base + end - 1,
                section=heading,
                metadata=dict(unit.metadata),
            )
            chunks.extend(
                _fit_unit(piece, strategy=strategy, size=size, overlap=overlap)
            )
    return chunks


def _split_markdown(text: str) -> tuple[tuple[str | None, str, int, int], ...]:
    lines = text.splitlines()
    if not lines:
        return ((None, text, 1, 1),)
    sections: list[tuple[str | None, list[str], int]] = []
    heading: str | None = None
    start = 1
    buf: list[str] = []
    for index, line in enumerate(lines, start=1):
        match = _HEADING.match(line)
        if match is None:
            buf.append(line)
            continue
        if buf or heading is not None:
            sections.append((heading, buf, start))
        heading = match.group(2).strip()
        buf = [line]
        start = index
    sections.append((heading, buf, start))
    if not any(item[0] for item in sections):
        return ((None, text, 1, max(len(lines), 1)),)
    result: list[tuple[str | None, str, int, int]] = []
    for heading, buf, start in sections:
        body = "\n".join(buf)
        end = start + max(len(buf) - 1, 0)
        result.append((heading, body, start, end))
    return tuple(result)


def _fit_all(
    units: tuple[ContentUnit, ...],
    strategy: str,
    *,
    size: int,
    overlap: int,
) -> list[ContentUnit]:
    chunks: list[ContentUnit] = []
    for unit in units:
        chunks.extend(_fit_unit(unit, strategy=strategy, size=size, overlap=overlap))
    return chunks


def _fit_unit(
    unit: ContentUnit, *, strategy: str, size: int, overlap: int
) -> list[ContentUnit]:
    if token_count(unit.content) <= size:
        return [_stamp(unit, strategy)]
    location = unit.location
    if location.page is not None:
        parts = window_text(unit.content, size=size, overlap=overlap)
        return [
            _rebuild(
                unit,
                content=part,
                strategy=strategy,
                chunk_key=str(index),
                page=location.page,
            )
            for index, part in enumerate(parts)
        ]
    base = location.line_start or 1
    spans = window_spans(unit.content, size=size, overlap=overlap)
    return [
        _rebuild(
            unit,
            content=content,
            strategy=strategy,
            chunk_key=str(index),
            line_start=base + start - 1,
            line_end=base + end - 1,
            section=location.section,
        )
        for index, (content, start, end) in enumerate(spans)
    ]


def _passthrough(units: tuple[ContentUnit, ...], strategy: str) -> list[ContentUnit]:
    return [_stamp(unit, strategy) for unit in units]


def _stamp(unit: ContentUnit, strategy: str) -> ContentUnit:
    metadata = dict(unit.metadata)
    metadata["strategy"] = strategy
    return unit.model_copy(update={"metadata": metadata})


def _rebuild(
    unit: ContentUnit,
    *,
    content: str,
    strategy: str,
    chunk_key: str,
    page: int | None = None,
    line_start: int | None = None,
    line_end: int | None = None,
    section: str | None = None,
) -> ContentUnit:
    location = unit.location
    metadata = dict(unit.metadata)
    metadata["strategy"] = strategy
    return make_unit(
        path=location.path or unit.unit_id,
        content=content,
        unit_type=unit.type,
        page=page,
        line_start=line_start,
        line_end=line_end,
        section=section if section is not None else location.section,
        metadata=metadata,
        chunk_key=chunk_key,
    )


def _number(units: list[ContentUnit]) -> tuple[ContentUnit, ...]:
    numbered: list[ContentUnit] = []
    for index, unit in enumerate(units):
        metadata = dict(unit.metadata)
        metadata["chunk_index"] = index
        numbered.append(unit.model_copy(update={"metadata": metadata}))
    return tuple(numbered)
