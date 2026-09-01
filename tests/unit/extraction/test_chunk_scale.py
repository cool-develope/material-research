from material_platform.classification import classify_files
from material_platform.extraction import MaterialFile, extract_units
from material_platform.extraction.window import DEFAULT_CHUNK_TOKENS, token_count
from tests.unit.helpers.docx import build_docx
from tests.unit.helpers.pdf import build_text_pdf
from tests.unit.helpers.text import numbered_words, word_count

_LONG = 12_000


def test_plain_text_over_10k_tokens_keeps_head_and_tail() -> None:
    text = numbered_words(_LONG, "tok")
    assert word_count(text) == _LONG
    item = MaterialFile(path="paper.txt", data=text.encode())
    units = extract_units(classify_files(("paper.txt",)), (item,))
    assert len(units) > 20
    assert all(unit.metadata["strategy"] == "document.window" for unit in units)
    assert all(token_count(unit.content) <= DEFAULT_CHUNK_TOKENS for unit in units)
    assert "tok00000" in units[0].content
    assert f"tok{_LONG - 1:05d}" in units[-1].content
    assert units[0].location.line_start == 1
    assert units[-1].location.line_end is not None
    assert units[-1].location.line_end >= units[0].location.line_end


def test_pdf_over_10k_tokens_keeps_every_page() -> None:
    pages = [numbered_words(400, f"p{index:02d}t").strip() for index in range(1, 31)]
    pages[-1] += " lastpage_unique_marker"
    item = MaterialFile(path="paper.pdf", data=build_text_pdf(pages))
    units = extract_units(classify_files(("paper.pdf",)), (item,))
    assert word_count(" ".join(pages)) > 10_000
    assert len(units) == 30
    assert [unit.location.page for unit in units] == list(range(1, 31))
    assert "lastpage_unique_marker" in units[-1].content
    assert all(unit.metadata["strategy"] == "document.pages" for unit in units)


def test_markdown_long_sections_keep_headings_and_tail() -> None:
    parts = ["# Introduction\n", numbered_words(900, "intro")]
    for index in range(10):
        parts.append(f"## Topic {index:02d}\n")
        parts.append(numbered_words(900, f"top{index:02d}"))
    parts.append("# Conclusion\n")
    parts.append(numbered_words(900, "concl"))
    parts.append("final_marker_token\n")
    text = "".join(parts)
    assert word_count(text) > 10_000
    item = MaterialFile(path="notes.md", data=text.encode())
    units = extract_units(classify_files(("notes.md",)), (item,))
    sections = {unit.location.section for unit in units}
    assert "Introduction" in sections
    assert "Topic 09" in sections
    assert "Conclusion" in sections
    assert all(unit.metadata["strategy"] == "document.sections" for unit in units)
    assert any("final_marker_token" in unit.content for unit in units)
    assert len(units) > 20


def test_docx_over_10k_tokens_keeps_tail() -> None:
    body = numbered_words(_LONG, "docw")
    item = MaterialFile(
        path="notes.docx",
        data=build_docx(paragraphs=tuple(body.splitlines())),
    )
    units = extract_units(classify_files(("notes.docx",)), (item,))
    joined = "\n".join(unit.content for unit in units)
    assert word_count(body) == _LONG
    assert len(units) > 20
    assert "docw00000" in units[0].content
    assert f"docw{_LONG - 1:05d}" in joined
    assert "word/document.xml" not in joined
    assert all(
        unit.metadata["strategy"] in {"document.window", "document.sections"}
        for unit in units
    )


def test_wide_project_caps_files_not_chunks() -> None:
    main = numbered_words(3_000, "main")
    files = [
        MaterialFile(path="pyproject.toml", data=b"[project]\nname='wide'\n"),
        MaterialFile(path="src/main.py", data=main.encode()),
        MaterialFile(
            path="src/api.py",
            data=b"def handle_request():\n    return 1\n",
        ),
        MaterialFile(path="src/util.py", data=b"def helper():\n    return 0\n"),
        MaterialFile(path="uv.lock", data=b"placeholder\n"),
        MaterialFile(path="docs/guide.md", data=b"# Guide\n"),
        *[
            MaterialFile(
                path=f"src/api_{index:02d}.py",
                data=(
                    f"def handle_request_{index:02d}():\n"
                    f"    return {index}\n"
                ).encode(),
            )
            for index in range(40)
        ],
        *[
            MaterialFile(
                path=f"tests/test_{index:02d}.py",
                data=f"def test_{index:02d}() -> None:\n    assert True\n".encode(),
            )
            for index in range(25)
        ],
    ]
    units = extract_units(
        classify_files(tuple(item.path for item in files)),
        tuple(files),
    )
    paths = [unit.location.path for unit in units]
    unique_paths = {path for path in paths if path}
    assert len(unique_paths) == 20
    assert len(units) > 20
    assert "pyproject.toml" in unique_paths
    assert "src/main.py" in unique_paths
    assert "src/api.py" in unique_paths
    assert "src/util.py" not in unique_paths
    assert "uv.lock" not in unique_paths
    assert "docs/guide.md" not in unique_paths
    assert not any(path.startswith("tests/") for path in unique_paths)
    assert "src/api_39.py" not in unique_paths
    mains = [unit for unit in units if unit.location.path == "src/main.py"]
    assert len(mains) > 1
    assert "main00000" in mains[0].content
    assert "main02999" in mains[-1].content
    assert all(unit.metadata["strategy"] == "code.file" for unit in units)
