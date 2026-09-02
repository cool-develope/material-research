from typing import Protocol

from material_platform.analysis.profile import MaterialProfile
from material_platform.classification.deterministic import ClassificationDecision
from material_platform.domain.analysis import MaterialAnalysis
from material_platform.domain.material import Material
from material_platform.domain.research_material import ContentUnit
from material_platform.extraction.common import MaterialFile


class Analyzer(Protocol):
    def analyze(
        self,
        material: Material,
        decision: ClassificationDecision,
        units: tuple[ContentUnit, ...],
        *,
        files: tuple[MaterialFile, ...] = (),
        profile: MaterialProfile | None = None,
    ) -> MaterialAnalysis: ...


class LlmClient(Protocol):
    def complete_json(self, prompt: str) -> dict[str, object]: ...
