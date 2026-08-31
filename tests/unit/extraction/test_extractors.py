from material_platform.classification import classify_files
from material_platform.extraction import MaterialFile, extract_units
from material_platform.extraction.pdf import extract_pdf
from material_platform.extraction.text import extract_text
from tests.unit.helpers.pdf import build_text_pdf


def test_text_extractor_sets_line_range() -> None:
    item = MaterialFile(path="src/main.py", data=b"print('ok')\nprint('again')\n")
    unit = extract_text(item)
    assert unit.location.path == "src/main.py"
    assert unit.location.line_start == 1
    assert unit.location.line_end == 2
    assert "print('ok')" in unit.content


def test_pdf_extractor_sets_page_location() -> None:
    item = MaterialFile(
        path="paper.pdf",
        data=build_text_pdf(["Introduction to materials", "Methods"]),
    )
    units = extract_pdf(item)
    assert len(units) == 2
    assert units[0].location.page == 1
    assert units[1].location.page == 2
    assert "Introduction" in units[0].content
    assert "Methods" in units[1].content


def test_project_extraction_includes_source_line_ranges() -> None:
    files = (
        MaterialFile(path="pyproject.toml", data=b"[project]\nname='backend'\n"),
        MaterialFile(path="src/main.py", data=b"print('ok')\n"),
        MaterialFile(path="docs/guide.md", data=b"# Guide\nDetails\n"),
    )
    decision = classify_files(tuple(item.path for item in files))
    units = extract_units(decision, files)
    by_path = {unit.location.path: unit for unit in units}
    assert by_path["src/main.py"].location.line_start == 1
    assert by_path["src/main.py"].location.line_end == 1
    assert by_path["docs/guide.md"].location.line_end == 2
