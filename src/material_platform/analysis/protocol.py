from typing import Protocol

from material_platform.classification.deterministic import ClassificationDecision
from material_platform.domain.analysis import MaterialAnalysis
from material_platform.domain.material import Material
from material_platform.domain.research_material import ContentUnit


class Analyzer(Protocol):
    def analyze(
        self,
        material: Material,
        decision: ClassificationDecision,
        units: tuple[ContentUnit, ...],
    ) -> MaterialAnalysis: ...


class LlmClient(Protocol):
    def complete_json(self, prompt: str) -> dict[str, object]: ...
