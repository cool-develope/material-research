from uuid import UUID

from pydantic import Field

from material_platform.domain.base import Contract
from material_platform.domain.enums import MaterialType


class ContentLocation(Contract):
    path: str | None = None
    page: int | None = Field(default=None, ge=1)
    line_start: int | None = Field(default=None, ge=1)
    line_end: int | None = Field(default=None, ge=1)
    section: str | None = None


class ContentUnit(Contract):
    unit_id: str
    type: str
    content: str
    location: ContentLocation
    digest: str
    metadata: dict[str, object] = Field(default_factory=dict)


class MaterialProvenance(Contract):
    source_id: UUID
    root_path: str
    origin_chain: tuple[str, ...] = ()


class ResearchMaterial(Contract):
    material_id: UUID
    material_type: MaterialType
    material_subtype: str | None
    title: str
    summary: str
    content_units: tuple[ContentUnit, ...]
    provenance: MaterialProvenance
    metadata: dict[str, object] = Field(default_factory=dict)
