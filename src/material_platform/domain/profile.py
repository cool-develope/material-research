from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from material_platform.domain.analysis import AnalysisCoverage, CoverageMode

PROFILE_PROCESSOR = "material-profiler"
PROFILE_VERSION = "v1"

DIRECT_TOKENS = 20_000
LEAF_TOKENS = 10_000
REDUCE_FANIN = 8
DEEP_FILES = 20


@dataclass(frozen=True)
class AnalysisBudgets:
    direct_tokens: int = DIRECT_TOKENS
    leaf_tokens: int = LEAF_TOKENS
    reduce_fanin: int = REDUCE_FANIN
    deep_files: int = DEEP_FILES


@dataclass(frozen=True)
class MaterialProfile:
    material_id: UUID
    kind: str
    mode: CoverageMode
    identity: dict[str, object] = field(default_factory=dict)
    structure: dict[str, object] = field(default_factory=dict)
    section_digests: tuple[dict[str, object], ...] = ()
    candidate_keywords: tuple[str, ...] = ()
    coverage: AnalysisCoverage = field(
        default_factory=lambda: AnalysisCoverage(mode="direct")
    )
    analysis_version: str = PROFILE_VERSION
    token_count: int = 0
    group_count: int = 0

    def as_dict(self) -> dict[str, object]:
        return {
            "material_id": str(self.material_id),
            "kind": self.kind,
            "mode": self.mode,
            "identity": self.identity,
            "structure": self.structure,
            "section_digests": list(self.section_digests),
            "candidate_keywords": list(self.candidate_keywords),
            "coverage": self.coverage.model_dump(mode="json"),
            "analysis_version": self.analysis_version,
            "token_count": self.token_count,
            "group_count": self.group_count,
        }
