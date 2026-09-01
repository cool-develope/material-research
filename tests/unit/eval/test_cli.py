from pathlib import Path

import pytest
from tests.unit.discovery.trees import SIMPLE_ZIP

from material_platform.application.cli import main as ingest_main
from material_platform.application.eval_cli import main as eval_main


def test_eval_retrieve_cli_scores_simple_mix(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    data_dir = tmp_path / "data"
    assert ingest_main([str(SIMPLE_ZIP), "--data-dir", str(data_dir), "--process"]) == 0
    capsys.readouterr()

    code = eval_main(["--data-dir", str(data_dir), "--lexical-only"])
    captured = capsys.readouterr()
    assert code == 0
    assert "lexical 3/3 hit@1" in captured.out
    assert "ok  api-handler" in captured.out
