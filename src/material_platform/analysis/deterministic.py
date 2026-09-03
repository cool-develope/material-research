from __future__ import annotations

import re
from pathlib import Path

from material_platform.analysis.keywords import from_units, grounded, unique
from material_platform.analysis.profiler import build_profile
from material_platform.classification.deterministic import ClassificationDecision
from material_platform.config import Settings
from material_platform.domain.analysis import AnalyzedEntity, MaterialAnalysis
from material_platform.domain.enums import MaterialType
from material_platform.domain.material import Material
from material_platform.domain.profile import MaterialProfile
from material_platform.domain.research_material import ContentUnit
from material_platform.extraction.common import MaterialFile

ANALYZER = "deterministic"
ANALYZER_VERSION = "v2"

_FUNC = re.compile(r"^\s*(?:async\s+)?def\s+([A-Za-z_]\w*)", re.MULTILINE)
_CLASS = re.compile(r"^\s*class\s+([A-Za-z_]\w*)", re.MULTILINE)
_IMPORT = re.compile(
    r"^(?:from\s+([\w.]+)\s+import|import\s+([\w.]+))",
    re.MULTILINE,
)
_JS_EXPORT = re.compile(
    r"(?:export\s+)?(?:async\s+)?(?:const|function|class|let|var)\s+([A-Za-z_]\w*)"
)
_HEADING = re.compile(r"^#{1,6}\s+(.+)$", re.MULTILINE)
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


class DeterministicAnalyzer:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings

    def analyze(
        self,
        material: Material,
        decision: ClassificationDecision,
        units: tuple[ContentUnit, ...],
        *,
        files: tuple[MaterialFile, ...] = (),
        profile: MaterialProfile | None = None,
    ) -> MaterialAnalysis:
        built = profile or build_profile(
            material,
            decision,
            units,
            files=files,
            settings=self._settings,
        )
        return _from_profile(material, decision, units, built)


def analyze_units(
    material: Material,
    decision: ClassificationDecision,
    units: tuple[ContentUnit, ...],
    *,
    files: tuple[MaterialFile, ...] = (),
) -> MaterialAnalysis:
    return DeterministicAnalyzer().analyze(
        material, decision, units, files=files
    )


def _from_profile(
    material: Material,
    decision: ClassificationDecision,
    units: tuple[ContentUnit, ...],
    profile: MaterialProfile,
) -> MaterialAnalysis:
    leaf = profile.section_digests[0] if profile.section_digests else {}
    summary = _string(leaf.get("summary")) or _fallback_summary(decision, units)
    title = _title(material, units, profile)
    pool = profile.candidate_keywords or from_units(units)
    keywords = grounded(list(pool), pool, limit=25)
    topics = unique(list(_strings(leaf.get("topics"))) + list(pool[:8]), limit=12)
    capabilities = _capabilities(profile)
    return MaterialAnalysis(
        material_id=material.material_id,
        title=title,
        summary=summary,
        purpose=_PURPOSE.get(decision.material_type),
        topics=topics,
        keywords=keywords,
        technologies=_technologies(decision, units, profile),
        capabilities=capabilities,
        entities=_entities(units),
        research_relevance=_RELEVANCE.get(decision.material_type, 0.4),
        analyzer=ANALYZER,
        analyzer_version=ANALYZER_VERSION,
        coverage=profile.coverage,
    )


def _title(
    material: Material,
    units: tuple[ContentUnit, ...],
    profile: MaterialProfile,
) -> str:
    for key in ("title", "package"):
        value = profile.identity.get(key)
        if isinstance(value, str) and value.strip():
            version = profile.identity.get("version")
            if key == "package" and isinstance(version, str) and version.strip():
                return f"{value.strip()} {version.strip()}"
            return value.strip()
    for unit in units:
        title = unit.metadata.get("title")
        if isinstance(title, str) and title.strip():
            return title.strip()
    headings = _HEADING.findall("\n".join(unit.content for unit in units[:4]))
    if headings:
        return headings[0].strip()
    return material.name


def _technologies(
    decision: ClassificationDecision,
    units: tuple[ContentUnit, ...],
    profile: MaterialProfile,
) -> tuple[str, ...]:
    names: list[str] = []
    if decision.subtype:
        names.append(decision.subtype)
    deps = profile.identity.get("dependencies")
    if isinstance(deps, list):
        names.extend(str(item) for item in deps)
    langs = profile.structure.get("languages")
    if isinstance(langs, dict):
        names.extend(str(item) for item in langs)
    for unit in units:
        for match in _IMPORT.finditer(unit.content):
            package = match.group(1) or match.group(2)
            if package:
                names.append(package.split(".", maxsplit=1)[0])
    return unique(names, limit=8)


def _capabilities(profile: MaterialProfile) -> tuple[str, ...]:
    names: list[str] = []
    for source in (profile.identity, profile.structure):
        value = source.get("entry_points")
        if isinstance(value, list):
            names.extend(str(item) for item in value if item)
    return unique(names, limit=12)


def _entities(
    units: tuple[ContentUnit, ...],
) -> tuple[AnalyzedEntity, ...]:
    found: list[AnalyzedEntity] = []
    seen: set[tuple[str, str]] = set()
    for unit in units:
        for match in _HEADING.finditer(unit.content):
            name = match.group(1).strip()
            key = ("heading", name.lower())
            if key in seen:
                continue
            seen.add(key)
            found.append(AnalyzedEntity(name=name, kind="heading"))
        location = unit.location
        for pattern, kind in ((_FUNC, "function"), (_CLASS, "class")):
            for match in pattern.finditer(unit.content):
                name = match.group(1)
                key = (kind, name.lower())
                if key in seen:
                    continue
                seen.add(key)
                found.append(AnalyzedEntity(name=name, kind=kind, location=location))
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


def _fallback_summary(
    decision: ClassificationDecision, units: tuple[ContentUnit, ...]
) -> str:
    count = len(units)
    kind = decision.material_type.value
    noun = "unit" if count == 1 else "units"
    return f"{count} {kind} {noun}"


def _string(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _strings(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return unique([str(item) for item in value if item], limit=12)
