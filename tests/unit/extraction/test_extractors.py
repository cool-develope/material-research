from io import BytesIO
from tarfile import TarFile, TarInfo
from zipfile import ZipFile

from material_platform.classification import classify_files
from material_platform.extraction import MaterialFile, extract_units
from material_platform.extraction.pdf import extract_pdf
from material_platform.extraction.text import extract_text
from tests.unit.helpers.docx import build_docx
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
    assert units[0].metadata["pages"] == 2


def test_pdf_extractor_keeps_info_metadata() -> None:
    item = MaterialFile(
        path="paper.pdf",
        data=build_text_pdf(
            ["Introduction to materials"],
            title="Survey of Alloys",
            author="Ada Lovelace",
        ),
    )
    units = extract_pdf(item)
    assert len(units) == 1
    assert units[0].location.page == 1
    assert units[0].metadata["title"] == "Survey of Alloys"
    assert units[0].metadata["author"] == "Ada Lovelace"
    assert units[0].metadata["pages"] == 1


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
    assert "docs/guide.md" not in by_path
    assert "pyproject.toml" in by_path


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
    go = [unit for unit in units if unit.location.path == "main.go"]
    assert decision.subtype == "go"
    handler = next(unit for unit in go if unit.location.section == "HandleRequest")
    assert handler.location.line_start == 3
    assert handler.location.line_end == 5
    assert "HandleRequest" in handler.content
    assert handler.metadata["strategy"] == "code.symbol"


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


def _tgz_bytes(entries: dict[str, bytes]) -> bytes:
    buffer = BytesIO()
    with TarFile.open(fileobj=buffer, mode="w:gz") as archive:
        for name, data in entries.items():
            info = TarInfo(name)
            info.size = len(data)
            archive.addfile(info, BytesIO(data))
    return buffer.getvalue()


def test_wheel_extractor_summarizes_metadata() -> None:
    item = MaterialFile(
        path="requests-2.32.3-py3-none-any.whl",
        data=_zip_bytes(
            {
                "requests-2.32.3.dist-info/METADATA": (
                    b"Name: requests\nVersion: 2.32.3\n"
                    b"Summary: HTTP for Humans\n"
                    b"Requires-Dist: urllib3\nRequires-Dist: certifi\n"
                ),
                "requests/__init__.py": b"x = 1\n",
            }
        ),
    )
    decision = classify_files((item.path,))
    units = extract_units(decision, (item,))
    assert len(units) == 1
    unit = units[0]
    assert "requests 2.32.3" in unit.content
    assert "urllib3" in unit.content
    assert "x = 1" not in unit.content
    assert unit.type == "artifact"
    assert unit.location.path == item.path
    assert unit.location.line_start is None
    assert unit.metadata["package"] == "requests"
    assert unit.metadata["version"] == "2.32.3"
    assert unit.metadata["dependencies"] == ["urllib3", "certifi"]
    assert unit.metadata["modules"] == ["requests"]


def test_npm_tarball_is_one_identity_unit() -> None:
    item = MaterialFile(
        path="left-pad-1.3.0.tgz",
        data=_tgz_bytes(
            {
                "package/package.json": (
                    b'{"name":"left-pad","version":"1.3.0",'
                    b'"description":"pad strings",'
                    b'"dependencies":{"is-number":"7.0.0"}}\n'
                ),
                "package/index.js": b"module.exports = function pad() {}\n",
            }
        ),
    )
    decision = classify_files((item.path,))
    units = extract_units(decision, (item,))
    assert decision.subtype == "node_tarball"
    assert len(units) == 1
    unit = units[0]
    assert unit.type == "artifact"
    assert "left-pad 1.3.0" in unit.content
    assert "module.exports" not in unit.content
    assert unit.location.line_start is None
    assert unit.metadata["package"] == "left-pad"
    assert unit.metadata["dependencies"] == ["is-number"]


def test_docx_keeps_core_properties() -> None:
    item = MaterialFile(
        path="notes.docx",
        data=build_docx(
            paragraphs=("Introduction to materials",),
            title="Lab Notes",
            author="Grace Hopper",
        ),
    )
    units = extract_units(classify_files((item.path,)), (item,))
    assert units[0].metadata["title"] == "Lab Notes"
    assert units[0].metadata["author"] == "Grace Hopper"
    assert "Introduction to materials" in units[0].content


def test_markdown_keeps_heading_title() -> None:
    item = MaterialFile(path="notes.md", data=b"# Survey\nBody text\n")
    units = extract_units(classify_files((item.path,)), (item,))
    assert units[0].metadata["title"] == "Survey"


def test_csv_keeps_column_names() -> None:
    item = MaterialFile(path="rows.csv", data=b"n,value\n1,2\n")
    units = extract_units(classify_files((item.path,)), (item,))
    assert units[0].metadata["columns"] == ["n", "value"]
    assert units[0].metadata["rows"] == 1


def test_project_records_dependencies_and_skips_node_modules() -> None:
    files = (
        MaterialFile(
            path="package.json",
            data=b'{"name":"frontend","dependencies":{"react":"18.2.0"}}\n',
        ),
        MaterialFile(path="src/app.js", data=b"export const n = 1;\n"),
        MaterialFile(
            path="node_modules/react/index.js",
            data=b"module.exports = {}\n",
        ),
    )
    decision = classify_files(tuple(item.path for item in files))
    units = extract_units(decision, files)
    paths = {unit.location.path for unit in units}
    assert paths == {"package.json", "src/app.js"}
    assert units[0].metadata["language"] == "node"
    assert units[0].metadata["package"] == "frontend"
    assert units[0].metadata["dependencies"] == ["react"]


def test_xlsx_stub_does_not_explode_xml() -> None:
    item = MaterialFile(
        path="grid.xlsx",
        data=_zip_bytes(
            {
                "[Content_Types].xml": b"<Types/>",
                "xl/workbook.xml": b"<workbook/>",
            }
        ),
    )
    decision = classify_files((item.path,))
    units = extract_units(decision, (item,))
    assert len(units) == 1
    assert units[0].type == "office"
    assert "xl/workbook.xml" not in units[0].content


def test_invalid_docx_does_not_index_xml() -> None:
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
    assert "word/document.xml" not in units[0].content


def test_binary_stub_for_installer() -> None:
    item = MaterialFile(path="setup.exe", data=b"MZ" + b"\x00" * 64)
    decision = classify_files((item.path,))
    units = extract_units(decision, (item,))
    assert len(units) == 1
    assert units[0].type == "binary"
    assert "installer" in units[0].content


def test_project_skips_tests_and_keeps_api() -> None:
    files = (
        MaterialFile(path="pyproject.toml", data=b"[project]\nname='backend'\n"),
        MaterialFile(path="src/main.py", data=b"print('ok')\n"),
        MaterialFile(path="src/api.py", data=b"def handle_request():\n    return 1\n"),
        MaterialFile(
            path="tests/test_main.py",
            data=b"def test_ok():\n    assert True\n",
        ),
        MaterialFile(path="docs/guide.md", data=b"# Guide\n"),
    )
    decision = classify_files(tuple(item.path for item in files))
    units = extract_units(decision, files)
    paths = {unit.location.path for unit in units}
    assert paths == {"pyproject.toml", "src/main.py", "src/api.py"}


def test_project_respects_unit_budget() -> None:
    files = (
        MaterialFile(path="pyproject.toml", data=b"[project]\nname='x'\n"),
        MaterialFile(path="src/main.py", data=b"print(0)\n"),
        *[
            MaterialFile(path=f"src/api_{index:02d}.py", data=b"x = 1\n")
            for index in range(25)
        ],
    )
    decision = classify_files(tuple(item.path for item in files))
    units = extract_units(decision, files, max_units=20)
    assert len(units) == 20
    paths = [unit.location.path for unit in units]
    assert paths[0] == "pyproject.toml"
    assert paths[1] == "src/main.py"
    assert "src/api_24.py" not in paths
