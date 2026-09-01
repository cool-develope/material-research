from __future__ import annotations

from collections.abc import Iterable

from material_platform.classification.deterministic import (
    CSV_SUFFIXES,
    ClassificationDecision,
)
from material_platform.domain.enums import MaterialType
from material_platform.domain.research_material import ContentUnit
from material_platform.extraction.artifact import extract_artifact
from material_platform.extraction.budget import DEFAULT_MAX_UNITS
from material_platform.extraction.chunk import chunk_units
from material_platform.extraction.common import MaterialFile
from material_platform.extraction.csv import extract_csv
from material_platform.extraction.docx import extract_docx
from material_platform.extraction.pdf import extract_pdf
from material_platform.extraction.project import extract_project
from material_platform.extraction.stub import (
    extract_stub,
    is_artifact_subtype,
    is_binary_subtype,
    is_docx_subtype,
    is_legacy_doc_subtype,
    is_stub_office_subtype,
)
from material_platform.extraction.text import extract_text
from material_platform.extraction.window import (
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_CHUNK_TOKENS,
)

EXTRACTOR = "extractors"
EXTRACTOR_VERSION = "v5"


def extract_units(
    decision: ClassificationDecision,
    files: tuple[MaterialFile, ...],
    *,
    max_units: int = DEFAULT_MAX_UNITS,
    chunk_tokens: int = DEFAULT_CHUNK_TOKENS,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> tuple[ContentUnit, ...]:
    raw = _extract_complete(decision, files, max_units=max_units)
    return chunk_units(
        decision,
        raw,
        chunk_tokens=chunk_tokens,
        chunk_overlap=chunk_overlap,
    )


def _extract_complete(
    decision: ClassificationDecision,
    files: tuple[MaterialFile, ...],
    *,
    max_units: int,
) -> tuple[ContentUnit, ...]:
    if decision.material_type is MaterialType.PROJECT:
        return extract_project(files, max_units=max_units)
    if decision.material_type is MaterialType.DATASET:
        return tuple(extract_csv(item) for item in files)
    if decision.material_type is MaterialType.DOCUMENT and decision.subtype == "pdf":
        return _flatten(extract_pdf(item) for item in files)
    if is_docx_subtype(decision.subtype):
        return _flatten(extract_docx(item) for item in files)
    if is_legacy_doc_subtype(decision.subtype):
        return tuple(
            extract_stub(
                item,
                unit_type="office",
                content="Legacy Word document (doc)",
            )
            for item in files
        )
    if is_artifact_subtype(decision.subtype):
        return tuple(extract_artifact(item, decision.subtype) for item in files)
    if is_stub_office_subtype(decision.subtype):
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
    if item.suffix in {".docx", ".docm"}:
        return extract_docx(item)
    return (extract_text(item),)


def _flatten(groups: Iterable[tuple[ContentUnit, ...]]) -> tuple[ContentUnit, ...]:
    units: list[ContentUnit] = []
    for group in groups:
        units.extend(group)
    return tuple(units)
