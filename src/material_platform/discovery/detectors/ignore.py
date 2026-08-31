from pathlib import Path

from material_platform.discovery.boundary import BoundaryDecision, BoundaryResult
from material_platform.discovery.skips import IGNORE_DIR_NAMES


class IgnoreBoundaryDetector:
    def detect(self, path: Path) -> BoundaryResult | None:
        if path.name not in IGNORE_DIR_NAMES:
            return None
        return BoundaryResult(decision=BoundaryDecision.IGNORE, confidence=1.0)
