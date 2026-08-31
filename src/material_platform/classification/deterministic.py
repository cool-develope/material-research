from dataclasses import dataclass
from pathlib import Path

from material_platform.discovery.detectors.project import PROJECT_MARKERS
from material_platform.domain.enums import MaterialType

CLASSIFIER = "deterministic"
CLASSIFIER_VERSION = "v1"

PDF_SUFFIXES = frozenset({".pdf"})
TEXT_SUFFIXES = frozenset({".txt", ".md", ".rst"})
CSV_SUFFIXES = frozenset({".csv", ".tsv"})
CODE_SUFFIXES = frozenset({".py", ".js", ".ts", ".tsx", ".jsx", ".mjs", ".cjs"})


@dataclass(frozen=True)
class ClassificationDecision:
    material_type: MaterialType
    subtype: str | None
    confidence: float
    evidence: tuple[str, ...]


def classify_files(paths: tuple[str, ...]) -> ClassificationDecision:
    if not paths:
        return ClassificationDecision(MaterialType.UNKNOWN, None, 0.0, ())

    root_names = {Path(path).name for path in paths if "/" not in path}
    found = [marker for marker in PROJECT_MARKERS if marker in root_names]
    if found:
        subtype = PROJECT_MARKERS[found[0]]
        return ClassificationDecision(
            MaterialType.PROJECT,
            subtype,
            0.98,
            tuple(f"root marker:{marker}" for marker in found),
        )

    suffixes = tuple(Path(path).suffix.lower() for path in paths)

    if all(suffix in CSV_SUFFIXES for suffix in suffixes):
        return ClassificationDecision(
            MaterialType.DATASET,
            "csv",
            0.9,
            (f"csv_files:{len(paths)}",),
        )

    if all(suffix in PDF_SUFFIXES for suffix in suffixes):
        return ClassificationDecision(
            MaterialType.DOCUMENT,
            "pdf",
            0.95,
            (f"pdf_files:{len(paths)}",),
        )

    if all(suffix in TEXT_SUFFIXES for suffix in suffixes):
        subtype = "markdown" if any(item == ".md" for item in suffixes) else "text"
        return ClassificationDecision(
            MaterialType.DOCUMENT,
            subtype,
            0.9,
            (f"text_files:{len(paths)}",),
        )

    if all(suffix in CODE_SUFFIXES for suffix in suffixes):
        return ClassificationDecision(
            MaterialType.CODE,
            suffixes[0].lstrip("."),
            0.85,
            (f"code_files:{len(paths)}",),
        )

    return ClassificationDecision(MaterialType.UNKNOWN, None, 0.0, ("unmatched",))
