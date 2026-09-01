from pathlib import Path

import pytest

from material_platform.application.cli import main
from material_platform.application.query import main as query_main
from tests.unit.discovery.trees import (
    COMPLEX_MATERIALS,
    FIXTURE_ZIP,
    SIMPLE_ZIP,
    make_mixed_tree,
    zip_contents,
)
from tests.unit.helpers.pdf import build_text_pdf


def test_ingest_simple_mix_fixture_three_materials(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = main([str(SIMPLE_ZIP), "--data-dir", str(tmp_path / "data"), "--process"])
    captured = capsys.readouterr()
    assert code == 0
    assert "paper.pdf" in captured.out
    assert "backend/" in captured.out
    assert "dataset/" in captured.out
    assert "src/api.py lines " in captured.out
    assert "skipped:" in captured.out

    code = query_main(["handle_request", "--data-dir", str(tmp_path / "data")])
    queried = capsys.readouterr()
    assert code == 0
    assert queried.out.splitlines()[0].startswith("1.")
    assert "src/api.py lines " in queried.out.splitlines()[0]


def test_ingest_local_cli_prints_tree(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    mixed = make_mixed_tree(tmp_path / "mixed")
    archive = zip_contents(mixed, tmp_path / "research.zip")

    code = main([str(archive), "--data-dir", str(tmp_path / "data")])
    captured = capsys.readouterr()

    assert code == 0
    assert "SOURCE" in captured.out
    assert "research.zip" in captured.out
    assert "MATERIAL" in captured.out
    assert "project candidate" in captured.out


def test_ingest_local_cli_process_prints_research_locations(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    mixed = make_mixed_tree(tmp_path / "mixed")
    archive = zip_contents(mixed, tmp_path / "research.zip")

    code = main([str(archive), "--data-dir", str(tmp_path / "data"), "--process"])
    captured = capsys.readouterr()

    assert code == 0
    assert "RESEARCH" in captured.out
    assert "page 1" in captured.out
    assert "lines " in captured.out
    assert "keywords:" in captured.out


def test_ingest_local_cli_process_complex_fixture(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = main([str(FIXTURE_ZIP), "--data-dir", str(tmp_path / "data"), "--process"])
    captured = capsys.readouterr()

    assert code == 0
    for path in COMPLEX_MATERIALS:
        assert path in captured.out
    assert "page 1" in captured.out
    assert "src/app.js lines " in captured.out
    assert "snippet.py lines " in captured.out
    assert "skipped:" in captured.out


def test_research_query_cli_prints_citations(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    mixed = make_mixed_tree(tmp_path / "mixed")
    archive = zip_contents(mixed, tmp_path / "research.zip")
    data_dir = tmp_path / "data"
    assert main([str(archive), "--data-dir", str(data_dir), "--process"]) == 0
    capsys.readouterr()

    code = query_main(["Introduction to materials", "--data-dir", str(data_dir)])
    captured = capsys.readouterr()
    assert code == 0
    assert "paper.pdf page 1" in captured.out
    assert "backend/" in captured.out
    assert "dataset/" in captured.out

    code = query_main(["handle_request", "--data-dir", str(data_dir)])
    captured = capsys.readouterr()
    assert code == 0
    assert captured.out.splitlines()[0].startswith("1.")
    assert "src/api.py lines " in captured.out.splitlines()[0]

    code = query_main(
        [
            "handle_request",
            "--data-dir",
            str(data_dir),
            "--material-type",
            "project",
        ]
    )
    captured = capsys.readouterr()
    assert code == 0
    assert "src/api.py lines " in captured.out

    code = query_main(
        [
            "handle_request",
            "--data-dir",
            str(data_dir),
            "--material-type",
            "document",
        ]
    )
    captured = capsys.readouterr()
    assert code == 0
    assert "src/api.py" not in captured.out


def test_ingest_long_pdf_compacts_locations(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    pdf = tmp_path / "long.pdf"
    pdf.write_bytes(build_text_pdf([f"page {index}" for index in range(1, 26)]))
    code = main([str(pdf), "--data-dir", str(tmp_path / "data"), "--process"])
    captured = capsys.readouterr()
    assert code == 0
    assert "25 units" in captured.out or "25 pages" in captured.out
    assert "…" in captured.out
    assert captured.out.count("page 25") == 1
