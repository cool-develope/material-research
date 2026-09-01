from __future__ import annotations

import re

from material_platform.domain.research_material import ContentUnit
from material_platform.extraction.common import make_unit

_PYTHON = re.compile(
    r"^(?P<indent>[ \t]*)(?:async[ \t]+)?(?:def|class)[ \t]+(?P<name>[A-Za-z_]\w*)"
)
_DECORATOR = re.compile(r"^[ \t]*@")


def split_python_symbols(unit: ContentUnit) -> tuple[ContentUnit, ...]:
    lines = unit.content.splitlines()
    marks = _top_level(lines)
    if not marks:
        return ()
    path = unit.location.path or unit.unit_id
    base = unit.location.line_start or 1
    extra = dict(unit.metadata)
    pieces: list[ContentUnit] = []
    first = marks[0][0]
    if first > 1:
        preamble = "\n".join(lines[: first - 1]).rstrip()
        if preamble.strip():
            pieces.append(
                make_unit(
                    path=path,
                    content=preamble,
                    unit_type=unit.type,
                    line_start=base,
                    line_end=base + first - 2,
                    metadata=extra,
                )
            )
    for index, (start, name) in enumerate(marks):
        last = marks[index + 1][0] - 1 if index + 1 < len(marks) else len(lines)
        body = "\n".join(lines[start - 1 : last])
        meta = dict(extra)
        meta["symbol"] = name
        pieces.append(
            make_unit(
                path=path,
                content=body,
                unit_type="symbol",
                line_start=base + start - 1,
                line_end=base + last - 1,
                section=name,
                metadata=meta,
            )
        )
    return tuple(pieces)


def _top_level(lines: list[str]) -> tuple[tuple[int, str], ...]:
    found: list[tuple[int, str]] = []
    for index, line in enumerate(lines, start=1):
        match = _PYTHON.match(line)
        if match is None or match.group("indent"):
            continue
        start = _decorator_start(lines, index)
        found.append((start, match.group("name")))
    return tuple(found)


def _decorator_start(lines: list[str], def_line: int) -> int:
    start = def_line
    index = def_line - 1
    while index >= 1 and _DECORATOR.match(lines[index - 1]):
        start = index
        index -= 1
    return start
