from material_platform.application.research_agent import main


def test_research_agent_cli_missing_db(tmp_path, capsys) -> None:
    code = main(["handle_request", "--data-dir", str(tmp_path / "missing")])
    captured = capsys.readouterr()
    assert code == 1
    assert "database not found" in captured.err
