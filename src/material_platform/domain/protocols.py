from typing import Protocol

from material_platform.domain.analysis import MaterialAnalysis
from material_platform.domain.classification import ClassificationDecision
from material_platform.domain.material import Material
from material_platform.domain.profile import MaterialProfile
from material_platform.domain.research_material import ContentUnit, MaterialFile


class LlmClient(Protocol):
    def complete_json(self, prompt: str) -> dict[str, object]: ...


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
