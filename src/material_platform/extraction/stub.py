from __future__ import annotations

from pathlib import Path

from material_platform.discovery.formats import (
    ARTIFACT_FORMATS,
    BINARY_FORMATS,
    DOCX_FORMATS,
    LEGACY_DOC_FORMATS,
    OFFICE_FORMATS,
    STUB_OFFICE_FORMATS,
)
from material_platform.discovery.peek import peek_zip_bytes
from material_platform.domain.research_material import ContentUnit
from material_platform.extraction.common import MaterialFile, make_unit


def extract_artifact(item: MaterialFile, subtype: str | None) -> ContentUnit:
    kind = subtype or "artifact"
    stem = Path(item.path).name
    if kind in {"python_wheel", "python_egg", "java_jar", "java_war"}:
        peek = peek_zip_bytes(item.data, kind, Path(item.path).stem)
        content = peek.summary
    else:
        content = f"{kind} artifact"
    return make_unit(
        path=item.path,
        content=content,
        unit_type="artifact",
        line_start=1,
        line_end=1,
        metadata={"format": kind, "filename": stem},
    )


def extract_stub(
    item: MaterialFile,
    *,
    unit_type: str,
    content: str,
    extra: dict[str, object] | None = None,
) -> ContentUnit:
    return make_unit(
        path=item.path,
        content=content,
        unit_type=unit_type,
        line_start=1,
        line_end=1,
        metadata={"filename": item.path, **(extra or {})},
    )


def is_artifact_subtype(subtype: str | None) -> bool:
    return subtype in ARTIFACT_FORMATS


def is_office_subtype(subtype: str | None) -> bool:
    return subtype in OFFICE_FORMATS


def is_docx_subtype(subtype: str | None) -> bool:
    return subtype in DOCX_FORMATS


def is_legacy_doc_subtype(subtype: str | None) -> bool:
    return subtype in LEGACY_DOC_FORMATS


def is_stub_office_subtype(subtype: str | None) -> bool:
    return subtype in STUB_OFFICE_FORMATS


def is_binary_subtype(subtype: str | None) -> bool:
    return subtype in BINARY_FORMATS
