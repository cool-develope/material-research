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


def test_classifies_wheel_as_code() -> None:
    decision = classify_files(("requests-2.32.3-py3-none-any.whl",))
    assert decision.material_type is MaterialType.CODE
    assert decision.subtype == "python_wheel"


def test_classifies_jar_as_code() -> None:
    decision = classify_files(("guava.jar",))
    assert decision.material_type is MaterialType.CODE
    assert decision.subtype == "java_jar"


def test_classifies_docx_as_document() -> None:
    decision = classify_files(("notes.docx",))
    assert decision.material_type is MaterialType.DOCUMENT
    assert decision.subtype == "docx"


def test_classifies_exe_as_installer() -> None:
    decision = classify_files(("AndroidStudio-setup.exe",))
    assert decision.material_type is MaterialType.UNKNOWN
    assert decision.subtype == "installer"


def test_classifies_go_project_from_root_marker() -> None:
    decision = classify_files(("go.mod", "main.go"))
    assert decision.material_type is MaterialType.PROJECT
    assert decision.subtype == "go"


def test_classifies_notebook_as_code() -> None:
    decision = classify_files(("notes.ipynb",))
    assert decision.material_type is MaterialType.CODE
    assert decision.subtype == "ipynb"
