from __future__ import annotations

import re
from collections.abc import Callable

from material_platform.domain.research_material import ContentUnit
from material_platform.extraction.common import make_unit

_PYTHON = re.compile(
    r"^(?P<indent>[ \t]*)(?:async[ \t]+)?(?:def|class)[ \t]+(?P<name>[A-Za-z_]\w*)"
)
_GO = re.compile(
    r"^func[ \t]+(?:\([^)]*\)[ \t]+)?(?P<fname>[A-Za-z_]\w*)"
    r"|^type[ \t]+(?P<tname>[A-Za-z_]\w*)"
)
_JS = re.compile(
    r"^(?:export[ \t]+(?:default[ \t]+)?)?(?:async[ \t]+)?function[ \t]+"
    r"(?P<fname>[A-Za-z_$][\w$]*)"
    r"|^(?:export[ \t]+(?:default[ \t]+)?)?class[ \t]+"
    r"(?P<cname>[A-Za-z_$][\w$]*)"
)
_DECORATOR = re.compile(r"^[ \t]*@")
_JS_SUFFIXES = (".js", ".mjs", ".cjs", ".jsx")

Marks = tuple[tuple[int, str], ...]
MarkFn = Callable[[list[str]], Marks]


def split_symbols(unit: ContentUnit) -> tuple[ContentUnit, ...]:
    path = (unit.location.path or "").lower()
    if path.endswith(".py"):
        return _split(unit, _python_marks)
    if path.endswith(".go"):
        return _split(unit, _go_marks)
    if path.endswith(_JS_SUFFIXES):
        return _split(unit, _js_marks)
    return ()


def split_python_symbols(unit: ContentUnit) -> tuple[ContentUnit, ...]:
    return _split(unit, _python_marks)


def _split(unit: ContentUnit, marks_for: MarkFn) -> tuple[ContentUnit, ...]:
    lines = unit.content.splitlines()
    marks = marks_for(lines)
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


def _python_marks(lines: list[str]) -> Marks:
    found: list[tuple[int, str]] = []
    for index, line in enumerate(lines, start=1):
        match = _PYTHON.match(line)
        if match is None or match.group("indent"):
            continue
        found.append((_decorator_start(lines, index), match.group("name")))
    return tuple(found)


def _go_marks(lines: list[str]) -> Marks:
    found: list[tuple[int, str]] = []
    for index, line in enumerate(lines, start=1):
        match = _GO.match(line)
        if match is None:
            continue
        found.append((index, match.group("fname") or match.group("tname")))
    return tuple(found)


def _js_marks(lines: list[str]) -> Marks:
    found: list[tuple[int, str]] = []
    for index, line in enumerate(lines, start=1):
        match = _JS.match(line)
        if match is None:
            continue
        found.append(
            (
                _decorator_start(lines, index),
                match.group("fname") or match.group("cname"),
            )
        )
    return tuple(found)


def _decorator_start(lines: list[str], def_line: int) -> int:
    start = def_line
    index = def_line - 1
    while index >= 1 and _DECORATOR.match(lines[index - 1]):
        start = index
        index -= 1
    return start
