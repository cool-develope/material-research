from __future__ import annotations

from collections.abc import Iterable

from material_platform.classification.deterministic import (
    CSV_SUFFIXES,
    ClassificationDecision,
)
from material_platform.domain.enums import MaterialType
from material_platform.domain.research_material import ContentUnit
from material_platform.extraction.common import MaterialFile
from material_platform.extraction.csv import extract_csv
from material_platform.extraction.pdf import extract_pdf
from material_platform.extraction.project import extract_project
from material_platform.extraction.stub import (
    extract_artifact,
    extract_stub,
    is_artifact_subtype,
    is_binary_subtype,
    is_office_subtype,
)
from material_platform.extraction.text import extract_text

EXTRACTOR = "extractors"
EXTRACTOR_VERSION = "v1"


def extract_units(
    decision: ClassificationDecision,
    files: tuple[MaterialFile, ...],
) -> tuple[ContentUnit, ...]:
    if decision.material_type is MaterialType.PROJECT:
        return extract_project(files)
    if decision.material_type is MaterialType.DATASET:
        return tuple(extract_csv(item) for item in files)
    if decision.material_type is MaterialType.DOCUMENT and decision.subtype == "pdf":
        return _flatten(extract_pdf(item) for item in files)
    if is_artifact_subtype(decision.subtype):
        return tuple(extract_artifact(item, decision.subtype) for item in files)
    if is_office_subtype(decision.subtype):
        return tuple(
            extract_stub(
                item,
                unit_type="office",
                content=f"Office document ({decision.subtype})",
            )
            for item in files
        )
    if is_binary_subtype(decision.subtype):
        return tuple(
            extract_stub(
                item,
                unit_type="binary",
                content=f"Binary or installer ({decision.subtype})",
                extra={"size": len(item.data)},
            )
            for item in files
        )
    if decision.material_type in {MaterialType.DOCUMENT, MaterialType.CODE}:
        return tuple(extract_text(item) for item in files)
    return _flatten(_extract_by_suffix(item) for item in files)


def _extract_by_suffix(item: MaterialFile) -> tuple[ContentUnit, ...]:
    if item.suffix == ".pdf":
        return extract_pdf(item)
    if item.suffix in CSV_SUFFIXES:
        return (extract_csv(item),)
    return (extract_text(item),)


def _flatten(groups: Iterable[tuple[ContentUnit, ...]]) -> tuple[ContentUnit, ...]:
    units: list[ContentUnit] = []
    for group in groups:
        units.extend(group)
    return tuple(units)
