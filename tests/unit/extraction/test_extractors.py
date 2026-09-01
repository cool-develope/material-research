from io import BytesIO
from zipfile import ZipFile

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


def test_go_project_extraction_includes_go_line_ranges() -> None:
    files = (
        MaterialFile(path="go.mod", data=b"module example.com/tools\n"),
        MaterialFile(
            path="main.go",
            data=b"package main\n\nfunc HandleRequest() string {\n\treturn \"ok\"\n}\n",
        ),
    )
    decision = classify_files(tuple(item.path for item in files))
    units = extract_units(decision, files)
    by_path = {unit.location.path: unit for unit in units}
    assert decision.subtype == "go"
    assert by_path["main.go"].location.line_start == 1
    assert by_path["main.go"].location.line_end == 5
    assert "HandleRequest" in by_path["main.go"].content


def test_notebook_extraction_uses_json_line_range() -> None:
    item = MaterialFile(
        path="notes.ipynb",
        data=b'{\n "cells": [],\n "nbformat": 4\n}\n',
    )
    decision = classify_files((item.path,))
    units = extract_units(decision, (item,))
    assert len(units) == 1
    assert units[0].location.path == "notes.ipynb"
    assert units[0].location.line_start == 1
    assert units[0].location.line_end == 4


def _zip_bytes(entries: dict[str, bytes]) -> bytes:
    buffer = BytesIO()
    with ZipFile(buffer, "w") as archive:
        for name, data in entries.items():
            archive.writestr(name, data)
    return buffer.getvalue()


def test_wheel_extractor_summarizes_metadata() -> None:
    item = MaterialFile(
        path="requests-2.32.3-py3-none-any.whl",
        data=_zip_bytes(
            {
                "requests-2.32.3.dist-info/METADATA": (
                    b"Name: requests\nVersion: 2.32.3\n"
                ),
                "requests/__init__.py": b"x = 1\n",
            }
        ),
    )
    decision = classify_files((item.path,))
    units = extract_units(decision, (item,))
    assert len(units) == 1
    assert "requests 2.32.3" in units[0].content
    assert units[0].type == "artifact"


def test_office_stub_does_not_explode_xml() -> None:
    item = MaterialFile(
        path="notes.docx",
        data=_zip_bytes(
            {
                "[Content_Types].xml": b"<Types/>",
                "word/document.xml": b"<w:document/>",
            }
        ),
    )
    decision = classify_files((item.path,))
    units = extract_units(decision, (item,))
    assert len(units) == 1
    assert units[0].type == "office"
    assert "word/document.xml" not in units[0].content


def test_binary_stub_for_installer() -> None:
    item = MaterialFile(path="setup.exe", data=b"MZ" + b"\x00" * 64)
    decision = classify_files((item.path,))
    units = extract_units(decision, (item,))
    assert len(units) == 1
    assert units[0].type == "binary"
    assert "installer" in units[0].content
