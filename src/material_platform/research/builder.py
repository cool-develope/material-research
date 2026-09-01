from material_platform.classification.deterministic import ClassificationDecision
from material_platform.domain.analysis import MaterialAnalysis
from material_platform.domain.enums import MaterialType
from material_platform.domain.material import Material
from material_platform.domain.research_material import (
    ContentUnit,
    MaterialProvenance,
    ResearchMaterial,
)
from material_platform.domain.source import Source

RESEARCH_PROCESSOR = "research-builder"
RESEARCH_VERSION = "v1"

_LIFT = (
    "title",
    "author",
    "pages",
    "package",
    "version",
    "language",
    "dependencies",
    "modules",
    "format",
    "summary",
    "columns",
)


def build_research_material(
    material: Material,
    source: Source,
    decision: ClassificationDecision,
    units: tuple[ContentUnit, ...],
    analysis: MaterialAnalysis | None = None,
    skipped: tuple[str, ...] = (),
) -> ResearchMaterial:
    origin = material.metadata.get("origin_chain", [])
    chain = tuple(str(item) for item in origin) if isinstance(origin, list) else ()
    metadata: dict[str, object] = {
        "content_digest": material.content_digest,
        **_lifted(units),
    }
    if skipped:
        metadata["skipped"] = list(skipped)
    title = material.name
    summary = _summary(decision, units)
    extracted_title = metadata.get("title")
    if isinstance(extracted_title, str) and extracted_title.strip():
        title = extracted_title.strip()
    elif isinstance(metadata.get("package"), str):
        package = str(metadata["package"])
        version = metadata.get("version")
        title = (
            f"{package} {version}".strip()
            if isinstance(version, str) and version
            else package
        )
    if analysis is not None:
        title = analysis.title
        summary = analysis.summary
        metadata["topics"] = list(analysis.topics)
        metadata["technologies"] = list(analysis.technologies)
        metadata["analysis_version"] = analysis.analyzer_version
    return ResearchMaterial(
        material_id=material.material_id,
        material_type=decision.material_type,
        material_subtype=decision.subtype,
        title=title,
        summary=summary,
        content_units=units,
        provenance=MaterialProvenance(
            source_id=source.source_id,
            root_path=material.root_path,
            origin_chain=chain,
        ),
        metadata=metadata,
    )


def _lifted(units: tuple[ContentUnit, ...]) -> dict[str, object]:
    found: dict[str, object] = {}
    for unit in units:
        for key in _LIFT:
            if key in found:
                continue
            value = unit.metadata.get(key)
            if value not in (None, "", []):
                found[key] = value
    return found


def _summary(
    decision: ClassificationDecision, units: tuple[ContentUnit, ...]
) -> str:
    unit_count = len(units)
    files = len({unit.location.path for unit in units if unit.location.path})
    if decision.material_type is MaterialType.DOCUMENT and decision.subtype == "pdf":
        noun = "page" if unit_count == 1 else "pages"
        return f"{unit_count} {noun} PDF"
    if decision.material_type is MaterialType.PROJECT:
        language = decision.subtype or "software"
        noun = "file" if files == 1 else "files"
        return f"{language} project, {files} citable {noun}"
    if decision.material_type is MaterialType.DATASET:
        noun = "file" if files == 1 else "files"
        return f"CSV dataset, {files} {noun}"
    noun = "unit" if unit_count == 1 else "units"
    return f"{unit_count} content {noun}"
