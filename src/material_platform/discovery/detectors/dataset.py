from pathlib import Path

from material_platform.discovery.boundary import BoundaryDecision, BoundaryResult
from material_platform.discovery.skips import is_skipped_name
from material_platform.domain.discovery import BoundaryEvidence

CSV_SUFFIXES = frozenset({".csv", ".tsv"})
DATA_DIR_NAMES = frozenset({"data", "dataset", "datasets"})


class DatasetBoundaryDetector:
    def detect(self, path: Path) -> BoundaryResult | None:
        files: list[Path] = []
        has_subdir = False
        for entry in path.iterdir():
            if is_skipped_name(entry.name):
                continue
            if entry.is_dir():
                has_subdir = True
            elif entry.is_file():
                files.append(entry)

        csvs = [item for item in files if item.suffix.lower() in CSV_SUFFIXES]
        if not csvs or has_subdir:
            return None

        named = path.name.lower() in DATA_DIR_NAMES
        if not named and len(csvs) != len(files):
            return None

        return BoundaryResult(
            decision=BoundaryDecision.MATERIAL,
            confidence=0.9 if named else 0.85,
            material_hint="csv_dataset",
            evidence=(
                BoundaryEvidence(
                    rule="csv_files",
                    value=str(len(csvs)),
                    weight=0.9,
                ),
            ),
        )
