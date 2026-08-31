from pathlib import Path

import pytest

from material_platform.application.cli import main
from tests.unit.discovery.trees import (
    COMPLEX_MATERIALS,
    FIXTURE_ZIP,
    make_mixed_tree,
    zip_contents,
)


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

    code = main(
        [str(archive), "--data-dir", str(tmp_path / "data"), "--process"]
    )
    captured = capsys.readouterr()

    assert code == 0
    assert "RESEARCH" in captured.out
    assert "page 1" in captured.out
    assert "lines " in captured.out


def test_ingest_local_cli_process_complex_fixture(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = main(
        [str(FIXTURE_ZIP), "--data-dir", str(tmp_path / "data"), "--process"]
    )
    captured = capsys.readouterr()

    assert code == 0
    for path in COMPLEX_MATERIALS:
        assert path in captured.out
    assert "page 1" in captured.out
    assert "src/app.js lines " in captured.out
    assert "snippet.py lines " in captured.out
