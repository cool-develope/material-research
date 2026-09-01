from material_platform.classification import classify_files
from material_platform.extraction import MaterialFile, extract_units
from material_platform.index.tokens import tokenize
from tests.unit.helpers.docx import build_docx
from tests.unit.helpers.pdf import build_text_pdf


def test_pdf_keeps_all_pages_beyond_twenty() -> None:
    pages = tuple(f"page_{index:02d} unique" for index in range(1, 26))
    item = MaterialFile(path="paper.pdf", data=build_text_pdf(list(pages)))
    units = extract_units(classify_files(("paper.pdf",)), (item,))
    assert len(units) == 25
    assert units[-1].location.page == 25
    assert "page_25" in units[-1].content
    assert all(unit.metadata["strategy"] == "document.pages" for unit in units)
    assert [unit.metadata["chunk_index"] for unit in units] == list(range(25))


def test_long_pdf_page_windows_keep_page() -> None:
    words = " ".join(f"tok{index:03d}" for index in range(40))
    item = MaterialFile(path="paper.pdf", data=build_text_pdf([words]))
    units = extract_units(
        classify_files(("paper.pdf",)),
        (item,),
        chunk_tokens=10,
        chunk_overlap=2,
    )
    assert len(units) > 1
    assert all(unit.location.page == 1 for unit in units)
    assert all(unit.metadata["strategy"] == "document.pages" for unit in units)
    joined = " ".join(unit.content for unit in units)
    assert "tok000" in joined
    assert "tok039" in joined


def test_markdown_splits_on_headings() -> None:
    text = "# Introduction\nHello materials\n## Methods\nMeasure twice\n"
    item = MaterialFile(path="notes.md", data=text.encode())
    units = extract_units(classify_files(("notes.md",)), (item,))
    sections = [unit.location.section for unit in units]
    assert sections == ["Introduction", "Methods"]
    assert all(unit.metadata["strategy"] == "document.sections" for unit in units)
    assert "Hello materials" in units[0].content
    assert units[0].location.line_start == 1


def test_one_line_document_gets_distinct_line_ranges() -> None:
    text = " ".join(f"tok{index:05d}" for index in range(2_000))
    item = MaterialFile(path="paper.txt", data=text.encode())
    units = extract_units(classify_files(("paper.txt",)), (item,))
    assert len(units) > 1
    assert units[0].location.line_start == 1
    assert units[-1].location.line_end is not None
    assert units[-1].location.line_end > units[0].location.line_end
    assert f"tok{1999:05d}" in units[-1].content


def test_plain_text_windows_long_content() -> None:
    payload = " ".join(f"zz{index:03d}" for index in range(40))
    item = MaterialFile(path="notes.txt", data=payload.encode())
    units = extract_units(
        classify_files(("notes.txt",)),
        (item,),
        chunk_tokens=10,
        chunk_overlap=2,
    )
    assert len(units) > 1
    assert all(unit.metadata["strategy"] == "document.window" for unit in units)
    assert all(len(tokenize(unit.content)) <= 12 for unit in units)


def test_docx_cites_body_lines_not_xml() -> None:
    item = MaterialFile(
        path="notes.docx",
        data=build_docx(paragraphs=("Introduction to materials",)),
    )
    units = extract_units(classify_files(("notes.docx",)), (item,))
    assert units
    assert "Introduction to materials" in units[0].content
    assert "word/document.xml" not in units[0].content
    assert units[0].location.line_start == 1
    assert units[0].location.line_end >= 1
    assert units[0].metadata["strategy"] in {"document.window", "document.sections"}


def test_docx_heading_sets_section() -> None:
    item = MaterialFile(
        path="notes.docx",
        data=build_docx(
            sections=(
                (1, "Introduction", "Alpha topic"),
                (2, "Methods", "Beta topic"),
            )
        ),
    )
    units = extract_units(classify_files(("notes.docx",)), (item,))
    sections = [unit.location.section for unit in units]
    assert "Introduction" in sections
    assert "Methods" in sections
    assert all(unit.metadata["strategy"] == "document.sections" for unit in units)


def test_legacy_doc_is_stub() -> None:
    item = MaterialFile(path="old.doc", data=b"\xd0\xcf\x11\xe0" + b"\x00" * 32)
    units = extract_units(classify_files(("old.doc",)), (item,))
    assert len(units) == 1
    assert units[0].type == "office"
    assert "Legacy Word" in units[0].content
    assert units[0].metadata["strategy"] == "stub"


def test_long_project_file_windows_keep_path_lines() -> None:
    payload = "\n".join(f"value_{index:03d} = {index}" for index in range(80))
    files = (
        MaterialFile(path="pyproject.toml", data=b"[project]\nname='x'\n"),
        MaterialFile(path="src/main.py", data=payload.encode()),
    )
    units = extract_units(
        classify_files(tuple(item.path for item in files)),
        files,
        chunk_tokens=20,
        chunk_overlap=4,
    )
    mains = [unit for unit in units if unit.location.path == "src/main.py"]
    assert len(mains) > 1
    assert all(unit.metadata["strategy"] == "code.file" for unit in mains)
    assert all(unit.location.line_start is not None for unit in mains)
    assert mains[0].location.line_start == 1


def test_python_symbols_are_separate_units() -> None:
    text = (
        "import os\n"
        "\n"
        "@route\n"
        "def alpha():\n"
        "    return 1\n"
        "\n"
        "class Box:\n"
        "    def method(self):\n"
        "        return 2\n"
        "\n"
        "async def beta():\n"
        "    return 3\n"
    )
    files = (
        MaterialFile(path="pyproject.toml", data=b"[project]\nname='x'\n"),
        MaterialFile(path="src/api.py", data=text.encode()),
    )
    units = extract_units(classify_files(tuple(item.path for item in files)), files)
    api = [unit for unit in units if unit.location.path == "src/api.py"]
    names = [unit.location.section for unit in api]
    assert names == [None, "alpha", "Box", "beta"]
    assert all(unit.metadata["strategy"] == "code.symbol" for unit in api)
    alpha = next(unit for unit in api if unit.location.section == "alpha")
    box = next(unit for unit in api if unit.location.section == "Box")
    assert "@route" in alpha.content
    assert "def method" in box.content
    assert alpha.location.line_start == 3
    assert "import os" in next(
        unit for unit in api if unit.location.section is None
    ).content


def test_long_python_symbol_windows_keep_section() -> None:
    body = "\n".join(f"    value_{index:03d} = {index}" for index in range(80))
    text = f"def huge():\n{body}\n"
    files = (
        MaterialFile(path="pyproject.toml", data=b"[project]\nname='x'\n"),
        MaterialFile(path="src/api.py", data=text.encode()),
    )
    units = extract_units(
        classify_files(tuple(item.path for item in files)),
        files,
        chunk_tokens=20,
        chunk_overlap=4,
    )
    api = [unit for unit in units if unit.location.path == "src/api.py"]
    assert len(api) > 1
    assert all(unit.location.section == "huge" for unit in api)
    assert all(unit.metadata["strategy"] == "code.symbol" for unit in api)
    assert api[0].location.line_start == 1
    assert "value_000" in api[0].content
    assert "value_079" in api[-1].content
