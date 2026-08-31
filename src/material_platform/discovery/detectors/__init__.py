from material_platform.discovery.boundary import CompositeBoundaryDetector
from material_platform.discovery.detectors.dataset import DatasetBoundaryDetector
from material_platform.discovery.detectors.ignore import IgnoreBoundaryDetector
from material_platform.discovery.detectors.project import ProjectBoundaryDetector


def default_boundary_detector() -> CompositeBoundaryDetector:
    return CompositeBoundaryDetector(
        (
            IgnoreBoundaryDetector(),
            ProjectBoundaryDetector(),
            DatasetBoundaryDetector(),
        )
    )
