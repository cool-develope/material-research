from pathlib import Path

import pytest

from material_platform.application.cli import main
from tests.unit.discovery.trees import make_mixed_tree, zip_contents


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
