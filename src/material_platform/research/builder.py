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


def build_research_material(
    material: Material,
    source: Source,
    decision: ClassificationDecision,
    units: tuple[ContentUnit, ...],
    analysis: MaterialAnalysis | None = None,
) -> ResearchMaterial:
    origin = material.metadata.get("origin_chain", [])
    chain = tuple(str(item) for item in origin) if isinstance(origin, list) else ()
    metadata: dict[str, object] = {"content_digest": material.content_digest}
    title = material.name
    summary = _summary(decision, len(units))
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


def _summary(decision: ClassificationDecision, unit_count: int) -> str:
    if decision.material_type is MaterialType.DOCUMENT and decision.subtype == "pdf":
        noun = "page" if unit_count == 1 else "pages"
        return f"{unit_count} {noun} PDF"
    if decision.material_type is MaterialType.PROJECT:
        language = decision.subtype or "software"
        noun = "file" if unit_count == 1 else "files"
        return f"{language} project, {unit_count} citable {noun}"
    if decision.material_type is MaterialType.DATASET:
        noun = "file" if unit_count == 1 else "files"
        return f"CSV dataset, {unit_count} {noun}"
    noun = "unit" if unit_count == 1 else "units"
    return f"{unit_count} content {noun}"
