from __future__ import annotations

from material_platform.discovery.formats import (
    ARTIFACT_FORMATS,
    BINARY_FORMATS,
    DOCX_FORMATS,
    LEGACY_DOC_FORMATS,
    OFFICE_FORMATS,
    STUB_OFFICE_FORMATS,
)
from material_platform.domain.research_material import ContentUnit
from material_platform.extraction.common import MaterialFile, make_unit


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
