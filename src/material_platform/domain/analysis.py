from typing import Literal
from uuid import UUID

from pydantic import Field

from material_platform.domain.base import Contract
from material_platform.domain.research_material import ContentLocation

CoverageMode = Literal[
    "direct",
    "hierarchical",
    "structural_sample",
    "artifact_metadata",
]


class AnalyzedEntity(Contract):
    name: str
    kind: str
    location: ContentLocation | None = None


class AnalysisCoverage(Contract):
    mode: CoverageMode
    total_units: int | None = Field(default=None, ge=0)
    analyzed_units: int | None = Field(default=None, ge=0)
    total_files: int | None = Field(default=None, ge=0)
    structurally_scanned_files: int | None = Field(default=None, ge=0)
    deeply_analyzed_files: int | None = Field(default=None, ge=0)
    ratio: float | None = Field(default=None, ge=0, le=1)


class MaterialAnalysis(Contract):
    material_id: UUID
    title: str
    summary: str
    purpose: str | None = None
    topics: tuple[str, ...] = ()
    keywords: tuple[str, ...] = ()
    technologies: tuple[str, ...] = ()
    capabilities: tuple[str, ...] = ()
    entities: tuple[AnalyzedEntity, ...] = ()
    research_relevance: float | None = Field(default=None, ge=0, le=1)
    analyzer: str
    analyzer_version: str
    coverage: AnalysisCoverage
