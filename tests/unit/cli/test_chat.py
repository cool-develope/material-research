from material_platform.cli.chat import main


def test_research_agent_cli_missing_db(tmp_path, capsys) -> None:
    code = main(["handle_request", "--data-dir", str(tmp_path / "missing")])
    captured = capsys.readouterr()
    assert code == 1
    assert "database not found" in captured.err


def test_research_agent_cli_accepts_mode(tmp_path, capsys) -> None:
    code = main(
        ["handle_request", "--data-dir", str(tmp_path / "missing"), "--mode", "quick"]
    )
    captured = capsys.readouterr()
    assert code == 1
    assert "database not found" in captured.err


def test_research_agent_cli_accepts_thread_id(tmp_path, capsys) -> None:
    code = main(
        [
            "handle_request",
            "--data-dir",
            str(tmp_path / "missing"),
            "--thread-id",
            "thread-1",
        ]
    )
    captured = capsys.readouterr()
    assert code == 1
    assert "database not found" in captured.err
