from pathlib import Path

from material_platform.discovery.boundary import BoundaryDecision
from material_platform.discovery.detectors import default_boundary_detector
from material_platform.discovery.detectors.dataset import DatasetBoundaryDetector
from material_platform.discovery.detectors.ignore import IgnoreBoundaryDetector
from material_platform.discovery.detectors.project import ProjectBoundaryDetector


def test_ignore_detector_matches_node_modules(tmp_path: Path) -> None:
    junk = tmp_path / "node_modules"
    junk.mkdir()
    result = IgnoreBoundaryDetector().detect(junk)
    assert result is not None
    assert result.decision is BoundaryDecision.IGNORE


def test_project_detector_uses_root_markers_only(tmp_path: Path) -> None:
    project = tmp_path / "app"
    project.mkdir()
    (project / "README.md").write_text("hi")
    nested = project / "src"
    nested.mkdir()
    (nested / "package.json").write_text("{}")

    assert ProjectBoundaryDetector().detect(project) is None
    result = ProjectBoundaryDetector().detect(nested)
    assert result is not None
    assert result.material_hint == "node_project"


def test_dataset_detector_requires_csv_files(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset"
    dataset.mkdir()
    (dataset / "rows.csv").write_text("a,b\n1,2\n")
    result = DatasetBoundaryDetector().detect(dataset)
    assert result is not None
    assert result.decision is BoundaryDecision.MATERIAL
    assert result.material_hint == "csv_dataset"


def test_named_data_dir_with_csv_subdirs_is_dataset(tmp_path: Path) -> None:
    data = tmp_path / "data"
    nested = data / "run1"
    nested.mkdir(parents=True)
    (nested / "rows.csv").write_text("a,b\n1,2\n")
    result = DatasetBoundaryDetector().detect(data)
    assert result is not None
    assert result.material_hint == "csv_dataset"


def test_nested_project_inside_data_is_not_a_dataset(tmp_path: Path) -> None:
    data = tmp_path / "data"
    data.mkdir()
    (data / "rows.csv").write_text("a,b\n1,2\n")
    nested = data / "model"
    nested.mkdir()
    (nested / "pyproject.toml").write_text("[project]\nname='x'\n")
    assert DatasetBoundaryDetector().detect(data) is None


def test_composite_prefers_project_over_dataset(tmp_path: Path) -> None:
    mixed = tmp_path / "dataset"
    mixed.mkdir()
    (mixed / "pyproject.toml").write_text("[project]\nname='x'\n")
    (mixed / "rows.csv").write_text("a,b\n1,2\n")

    result = default_boundary_detector().detect(mixed)
    assert result.decision is BoundaryDecision.MATERIAL
    assert result.material_hint == "python_project"
