from material_platform.classification import classify_files
from material_platform.domain.enums import MaterialType


def test_classifies_python_project_from_root_marker() -> None:
    decision = classify_files(("pyproject.toml", "src/main.py", "tests/test_main.py"))
    assert decision.material_type is MaterialType.PROJECT
    assert decision.subtype == "python"
    assert "root marker:pyproject.toml" in decision.evidence


def test_classifies_pdf_document() -> None:
    decision = classify_files(("paper.pdf",))
    assert decision.material_type is MaterialType.DOCUMENT
    assert decision.subtype == "pdf"


def test_classifies_csv_dataset() -> None:
    decision = classify_files(("rows.csv", "extra.tsv"))
    assert decision.material_type is MaterialType.DATASET
    assert decision.subtype == "csv"


def test_classifies_markdown_as_document() -> None:
    decision = classify_files(("README.md", "notes.txt"))
    assert decision.material_type is MaterialType.DOCUMENT
    assert decision.subtype == "markdown"


def test_project_marker_beats_nested_csv() -> None:
    decision = classify_files(("package.json", "data/rows.csv"))
    assert decision.material_type is MaterialType.PROJECT
    assert decision.subtype == "node"
