from pathlib import Path

from material_platform.discovery.boundary import BoundaryDecision, BoundaryResult
from material_platform.domain.discovery import BoundaryEvidence

PROJECT_MARKERS: dict[str, str] = {
    "pyproject.toml": "python",
    "setup.py": "python",
    "requirements.txt": "python",
    "Pipfile": "python",
    "package.json": "node",
    "go.mod": "go",
    "Cargo.toml": "rust",
    "pom.xml": "java",
    "build.gradle": "java",
}


class ProjectBoundaryDetector:
    def detect(self, path: Path) -> BoundaryResult | None:
        names = {entry.name for entry in path.iterdir()}
        found = [marker for marker in PROJECT_MARKERS if marker in names]
        if not found:
            return None

        subtype = PROJECT_MARKERS[found[0]]
        return BoundaryResult(
            decision=BoundaryDecision.MATERIAL,
            confidence=0.98,
            material_hint=f"{subtype}_project",
            evidence=tuple(
                BoundaryEvidence(rule="root_marker", value=marker, weight=1.0)
                for marker in found
            ),
        )
