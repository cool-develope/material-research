from __future__ import annotations

from material_platform.analysis.document import extractive_leaf, hierarchical_digests
from material_platform.analysis.group import content_tokens, group_units
from material_platform.analysis.inventory import scan_project
from material_platform.analysis.keywords import from_units, unique
from material_platform.analysis.profile import (
    PROFILE_PROCESSOR,
    PROFILE_VERSION,
    AnalysisBudgets,
    MaterialProfile,
    budgets_of,
)
from material_platform.classification.deterministic import ClassificationDecision
from material_platform.config import Settings
from material_platform.discovery.formats import ARTIFACT_FORMATS
from material_platform.domain.analysis import AnalysisCoverage
from material_platform.domain.enums import MaterialType
from material_platform.domain.material import Material
from material_platform.domain.research_material import ContentUnit
from material_platform.extraction.common import MaterialFile

__all__ = ["PROFILE_PROCESSOR", "PROFILE_VERSION", "build_profile"]


def build_profile(
    material: Material,
    decision: ClassificationDecision,
    units: tuple[ContentUnit, ...],
    *,
    files: tuple[MaterialFile, ...] = (),
    settings: Settings | None = None,
) -> MaterialProfile:
    budgets = budgets_of(settings)
    if decision.subtype in ARTIFACT_FORMATS:
        return _artifact(material, units)
    if decision.material_type is MaterialType.PROJECT:
        return _project(material, units, files, budgets)
    if decision.material_type is MaterialType.DATASET:
        return _dataset(material, units)
    return _document(material, units, budgets)


def _document(
    material: Material,
    units: tuple[ContentUnit, ...],
    budgets: AnalysisBudgets,
) -> MaterialProfile:
    tokens = content_tokens(units)
    if tokens <= budgets.direct_tokens:
        leaves = (extractive_leaf(units),) if units else ()
        mode = "direct"
        groups = 1 if units else 0
    else:
        groups = len(group_units(units, target_tokens=budgets.leaf_tokens))
        leaves = hierarchical_digests(
            units,
            leaf_tokens=budgets.leaf_tokens,
            fan_in=budgets.reduce_fanin,
        )
        mode = "hierarchical"
    keywords = from_units(units, limit=80)
    return MaterialProfile(
        material_id=material.material_id,
        kind="document",
        mode=mode,
        identity=_identity(units),
        section_digests=leaves,
        candidate_keywords=keywords,
        coverage=AnalysisCoverage(
            mode=mode,
            total_units=len(units),
            analyzed_units=len(units),
            ratio=1.0 if units else 0.0,
        ),
        analysis_version=PROFILE_VERSION,
        token_count=tokens,
        group_count=groups,
    )


def _project(
    material: Material,
    units: tuple[ContentUnit, ...],
    files: tuple[MaterialFile, ...],
    budgets: AnalysisBudgets,
) -> MaterialProfile:
    records = scan_project(files) if files else ()
    scanned = len(records)
    deep_paths = {unit.location.path for unit in units if unit.location.path}
    if not records:
        scanned = len({unit.location.path for unit in units if unit.location.path})
    languages: dict[str, int] = {}
    subsystems: list[str] = []
    imports: list[str] = []
    for record in records:
        languages[record.language] = languages.get(record.language, 0) + 1
        if record.subsystem:
            subsystems.append(record.subsystem)
        imports.extend(record.imports)
    identity = _identity(units)
    if records:
        identity.setdefault("languages", languages)
    structure = {
        "languages": languages,
        "subsystems": list(unique(subsystems, limit=24)),
        "entry_points": [item.path for item in records if item.kind == "entry"][:8],
        "dependencies": list(unique(imports, limit=30)),
        "deep_files": sorted(path for path in deep_paths if path),
    }
    keywords = unique(
        list(from_units(units, limit=40))
        + [str(identity.get("package") or "")]
        + list(identity.get("dependencies") or [])
        + structure["dependencies"],
        limit=80,
    )
    total_files = scanned or len(deep_paths)
    deep = len(deep_paths) or min(len(units), budgets.deep_files)
    ratio = (deep / total_files) if total_files else 0.0
    return MaterialProfile(
        material_id=material.material_id,
        kind="project",
        mode="structural_sample",
        identity=identity,
        structure=structure,
        section_digests=(extractive_leaf(units),) if units else (),
        candidate_keywords=keywords,
        coverage=AnalysisCoverage(
            mode="structural_sample",
            total_units=len(units),
            analyzed_units=len(units),
            total_files=total_files,
            structurally_scanned_files=total_files,
            deeply_analyzed_files=deep,
            ratio=min(ratio, 1.0),
        ),
        analysis_version=PROFILE_VERSION,
        token_count=content_tokens(units),
        group_count=1,
    )


def _artifact(material: Material, units: tuple[ContentUnit, ...]) -> MaterialProfile:
    identity = _identity(units)
    keywords = from_units(units, limit=40)
    leaf = extractive_leaf(units) if units else {}
    return MaterialProfile(
        material_id=material.material_id,
        kind="artifact",
        mode="artifact_metadata",
        identity=identity,
        structure={
            "modules": identity.get("modules") or [],
            "dependencies": identity.get("dependencies") or [],
        },
        section_digests=(leaf,) if leaf else (),
        candidate_keywords=keywords,
        coverage=AnalysisCoverage(
            mode="artifact_metadata",
            total_units=len(units),
            analyzed_units=len(units),
            ratio=1.0 if units else 0.0,
        ),
        analysis_version=PROFILE_VERSION,
        token_count=content_tokens(units),
        group_count=1,
    )


def _dataset(material: Material, units: tuple[ContentUnit, ...]) -> MaterialProfile:
    identity = _identity(units)
    raw_columns = identity.get("columns")
    columns = raw_columns if isinstance(raw_columns, list) else []
    keywords = unique(
        [str(item) for item in columns] + list(from_units(units, limit=20)),
        limit=40,
    )
    return MaterialProfile(
        material_id=material.material_id,
        kind="dataset",
        mode="direct",
        identity=identity,
        structure={"columns": columns, "rows": identity.get("rows")},
        section_digests=(extractive_leaf(units),) if units else (),
        candidate_keywords=keywords,
        coverage=AnalysisCoverage(
            mode="direct",
            total_units=len(units),
            analyzed_units=len(units),
            ratio=1.0 if units else 0.0,
        ),
        analysis_version=PROFILE_VERSION,
        token_count=content_tokens(units),
        group_count=1,
    )


def _identity(units: tuple[ContentUnit, ...]) -> dict[str, object]:
    found: dict[str, object] = {}
    for unit in units:
        for key in (
            "title",
            "author",
            "package",
            "version",
            "language",
            "summary",
            "format",
            "rows",
            "columns",
            "dependencies",
            "modules",
            "entry_points",
            "keywords",
        ):
            if key in found:
                continue
            value = unit.metadata.get(key)
            if value not in (None, "", []):
                found[key] = value
    return found
