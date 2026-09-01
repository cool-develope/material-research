from pathlib import Path

from material_platform.discovery.boundary import BoundaryDecision, BoundaryResult
from material_platform.discovery.detectors.project import PROJECT_MARKERS
from material_platform.discovery.skips import is_skipped_name
from material_platform.domain.discovery import BoundaryEvidence

CSV_SUFFIXES = frozenset({".csv", ".tsv"})
DATA_DIR_NAMES = frozenset({"data", "dataset", "datasets"})


class DatasetBoundaryDetector:
    def detect(self, path: Path) -> BoundaryResult | None:
        files, nested_project = _tree_files(path)
        if nested_project or not files:
            return None
        csvs = [item for item in files if item.suffix.lower() in CSV_SUFFIXES]
        if not csvs:
            return None
        named = path.name.lower() in DATA_DIR_NAMES
        if named:
            return _result(len(csvs), named=True)
        if _has_kept_subdir(path):
            return None
        if any(item.suffix.lower() not in CSV_SUFFIXES for item in files):
            return None
        return _result(len(csvs), named=False)


def _result(count: int, *, named: bool) -> BoundaryResult:
    return BoundaryResult(
        decision=BoundaryDecision.MATERIAL,
        confidence=0.9 if named else 0.85,
        material_hint="csv_dataset",
        evidence=(
            BoundaryEvidence(rule="csv_files", value=str(count), weight=0.9),
        ),
    )


def _has_kept_subdir(path: Path) -> bool:
    return any(
        entry.is_dir() and not is_skipped_name(entry.name) for entry in path.iterdir()
    )


def _tree_files(path: Path) -> tuple[list[Path], bool]:
    files: list[Path] = []
    nested_project = False
    for item in path.rglob("*"):
        if not item.is_file():
            continue
        relative = item.relative_to(path)
        if any(is_skipped_name(part) for part in relative.parts):
            continue
        if item.name in PROJECT_MARKERS:
            nested_project = True
        files.append(item)
    return files, nested_project
