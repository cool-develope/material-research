from material_platform.cli import main


def test_mp_help(capsys) -> None:
    assert main(["--help"]) == 0
    out = capsys.readouterr().out
    assert "ingest" in out
    assert "serve" in out
    assert "eval-aiml" in out


def test_mp_unknown_command(capsys) -> None:
    assert main(["nope"]) == 1
    assert "unknown command: nope" in capsys.readouterr().err
