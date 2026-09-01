from uuid import UUID

from pydantic import Field

from material_platform.domain.base import Contract
from material_platform.domain.research_material import ContentLocation


class AnalyzedEntity(Contract):
    name: str
    kind: str
    location: ContentLocation | None = None


class MaterialAnalysis(Contract):
    material_id: UUID
    title: str
    summary: str
    purpose: str | None = None
    topics: tuple[str, ...] = ()
    technologies: tuple[str, ...] = ()
    entities: tuple[AnalyzedEntity, ...] = ()
    research_relevance: float | None = Field(default=None, ge=0, le=1)
    analyzer: str
    analyzer_version: str
