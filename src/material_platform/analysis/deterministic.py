from __future__ import annotations

import re
from pathlib import Path

from material_platform.classification.deterministic import ClassificationDecision
from material_platform.domain.analysis import AnalyzedEntity, MaterialAnalysis
from material_platform.domain.enums import MaterialType
from material_platform.domain.material import Material
from material_platform.domain.research_material import ContentUnit

ANALYZER = "deterministic"
ANALYZER_VERSION = "v1"

_HEADING = re.compile(r"^#{1,6}\s+(.+)$", re.MULTILINE)
_FUNC = re.compile(r"^\s*(?:async\s+)?def\s+([A-Za-z_]\w*)", re.MULTILINE)
_CLASS = re.compile(r"^\s*class\s+([A-Za-z_]\w*)", re.MULTILINE)
_IMPORT = re.compile(
    r"^(?:from\s+([\w.]+)\s+import|import\s+([\w.]+))",
    re.MULTILINE,
)
_JS_EXPORT = re.compile(
    r"(?:export\s+)?(?:async\s+)?(?:const|function|class|let|var)\s+([A-Za-z_]\w*)"
)
_WORD = re.compile(r"[A-Za-z][A-Za-z0-9_]{3,}")
_SENTENCE = re.compile(r"(?<=[.!?])\s+")
_STOP = frozenset(
    {
        "this",
        "that",
        "with",
        "from",
        "into",
        "return",
        "none",
        "true",
        "false",
        "self",
        "print",
    }
)
_PURPOSE = {
    MaterialType.DOCUMENT: "document for research reading",
    MaterialType.PROJECT: "software project",
    MaterialType.DATASET: "tabular dataset",
    MaterialType.CODE: "source code",
}
_RELEVANCE = {
    MaterialType.DOCUMENT: 0.8,
    MaterialType.PROJECT: 0.7,
    MaterialType.CODE: 0.6,
    MaterialType.DATASET: 0.5,
}


def analyze_units(
    material: Material,
    decision: ClassificationDecision,
    units: tuple[ContentUnit, ...],
) -> MaterialAnalysis:
    headings = _collect(_HEADING, units)
    entities = _entities(units, headings)
    technologies = _technologies(decision, units)
    topics = _topics(material, units, headings)
    return MaterialAnalysis(
        material_id=material.material_id,
        title=_title(material, headings),
        summary=_summary(decision, units),
        purpose=_PURPOSE.get(decision.material_type),
        topics=topics,
        technologies=technologies,
        entities=entities,
        research_relevance=_RELEVANCE.get(decision.material_type, 0.4),
        analyzer=ANALYZER,
        analyzer_version=ANALYZER_VERSION,
    )


def _title(material: Material, headings: tuple[str, ...]) -> str:
    if headings:
        return headings[0]
    return material.name


def _summary(
    decision: ClassificationDecision,
    units: tuple[ContentUnit, ...],
) -> str:
    for unit in units:
        text = unit.content.strip()
        if not text:
            continue
        parts = [part.strip() for part in _SENTENCE.split(text) if part.strip()]
        if parts:
            return " ".join(parts[:2])[:400]
    count = len(units)
    kind = decision.material_type.value
    noun = "unit" if count == 1 else "units"
    return f"{count} {kind} {noun}"


def _topics(
    material: Material,
    units: tuple[ContentUnit, ...],
    headings: tuple[str, ...],
) -> tuple[str, ...]:
    words: list[str] = []
    stem = Path(material.name).stem
    if stem and stem not in {"src", "backend", "frontend"}:
        words.append(stem)
    words.extend(headings)
    for unit in units:
        for match in _WORD.findall(unit.content):
            lowered = match.lower()
            if lowered not in _STOP:
                words.append(lowered)
    return _unique(words, limit=12)


def _technologies(
    decision: ClassificationDecision,
    units: tuple[ContentUnit, ...],
) -> tuple[str, ...]:
    names: list[str] = []
    if decision.subtype:
        names.append(decision.subtype)
    for unit in units:
        for match in _IMPORT.finditer(unit.content):
            package = match.group(1) or match.group(2)
            if package:
                names.append(package.split(".", maxsplit=1)[0])
    return _unique(names, limit=8)


def _entities(
    units: tuple[ContentUnit, ...],
    headings: tuple[str, ...],
) -> tuple[AnalyzedEntity, ...]:
    found: list[AnalyzedEntity] = []
    seen: set[tuple[str, str]] = set()
    for heading in headings:
        key = ("heading", heading.lower())
        if key not in seen:
            seen.add(key)
            found.append(AnalyzedEntity(name=heading, kind="heading"))
    for unit in units:
        location = unit.location
        for pattern, kind in ((_FUNC, "function"), (_CLASS, "class")):
            for match in pattern.finditer(unit.content):
                name = match.group(1)
                key = (kind, name.lower())
                if key in seen:
                    continue
                seen.add(key)
                found.append(
                    AnalyzedEntity(name=name, kind=kind, location=location)
                )
        if Path(unit.location.path or "").suffix.lower() in {".js", ".ts", ".tsx"}:
            for match in _JS_EXPORT.finditer(unit.content):
                name = match.group(1)
                key = ("export", name.lower())
                if key in seen:
                    continue
                seen.add(key)
                found.append(
                    AnalyzedEntity(name=name, kind="export", location=location)
                )
    return tuple(found[:24])


def _collect(
    pattern: re.Pattern[str],
    units: tuple[ContentUnit, ...],
) -> tuple[str, ...]:
    names: list[str] = []
    for unit in units:
        names.extend(match.strip() for match in pattern.findall(unit.content))
    return _unique(names, limit=12)


def _unique(items: list[str], *, limit: int) -> tuple[str, ...]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        key = item.strip()
        if not key:
            continue
        lowered = key.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        out.append(key)
        if len(out) >= limit:
            break
    return tuple(out)
