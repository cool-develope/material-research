import os
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import pytest
from docx import Document
from tests.unit.discovery.trees import EVAL_AIML_ZIP

from material_platform.application.local import ingest_and_process
from material_platform.eval import AIML_SUITE, LEXICAL, load_suite
from material_platform.eval.aiml import _eval_settings
from material_platform.eval.aiml_checks import discovery_errors, ingest_errors
from material_platform.eval.aiml_corpus import (
    AIML_ZIP,
    REQUIRED_LEXICAL_IDS,
    SOURCES,
    TRANSFORMERS_ROOT,
    expected_roots,
    make_suite,
)
from material_platform.eval.aiml_fetch import (
    alpaca_to_csv,
    markdown_to_docx,
    select_github_members,
)
from material_platform.eval.score import format_report, hit_at_1, score_suite


def test_aiml_sources_are_public_https() -> None:
    assert SOURCES
    for source in SOURCES:
        assert source.url.startswith("https://")
        for url in source.fallbacks:
            assert url.startswith("https://")


def test_aiml_suite_uses_real_phrases() -> None:
    suite = make_suite()
    loaded = load_suite(AIML_SUITE)
    assert loaded.id == "eval_aiml"
    assert {case.id for case in loaded.cases} == {case.id for case in suite.cases}
    queries = " ".join(case.query for case in suite.cases)
    assert "survey_head_marker" not in queries
    assert "4-bit NormalFloat" in queries
    assert "Speech and Language Processing" in queries
    lexical = [case for case in suite.cases if case.mode == LEXICAL]
    assert REQUIRED_LEXICAL_IDS <= {case.id for case in lexical}


def test_alpaca_to_csv_keeps_instruction() -> None:
    csv = alpaca_to_csv(
        [
            {
                "instruction": "Give three tips for staying healthy.",
                "input": "",
                "output": "Eat well.",
            }
        ]
    )
    assert "Give three tips for staying healthy" in csv
    assert csv.splitlines()[0] == "instruction,input,output"


def test_markdown_to_docx_is_real_docx() -> None:
    data = markdown_to_docx("# PEFT\nUse SFTTrainer with LoRA.\n", title="PEFT")
    assert data[:2] == b"PK"
    document = Document(BytesIO(data))
    text = "\n".join(paragraph.text for paragraph in document.paragraphs)
    assert "SFTTrainer" in text


def test_select_github_members_prefers_src_and_caps() -> None:
    names = (
        "repo-1.0/README.md",
        "repo-1.0/docs/guide.md",
        "repo-1.0/src/pkg/a.py",
        "repo-1.0/src/pkg/b.py",
        "repo-1.0/tests/test_a.py",
        "repo-1.0/weights.bin",
    )
    chosen = select_github_members(names, max_files=3)
    relative = [name.split("/", 1)[1] for name in chosen]
    assert "README.md" in relative
    assert "src/pkg/a.py" in relative
    assert "docs/guide.md" not in relative
    assert "weights.bin" not in relative
    assert len(chosen) == 3


def test_eval_aiml_settings_ignore_dotenv_knobs(tmp_path: Path) -> None:
    settings = _eval_settings(tmp_path / "data")
    assert settings.analyzer == "deterministic"
    assert settings.embedder == "fake"
    assert settings.reranker == "off"
    assert not settings.database_url.startswith("postgresql")


def test_eval_aiml_prod_preflight_exits_before_ingest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from material_platform.eval.aiml import main

    monkeypatch.setattr(
        "material_platform.eval.aiml.preflight_prod",
        lambda *args, **kwargs: ["postgres is not on 127.0.0.1:5432"],
    )
    assert main(["--prod", "--skip-build", "--skip-ingest"]) == 1


def test_eval_aiml_zip_skipped_if_missing() -> None:
    if AIML_ZIP.exists():
        pytest.skip("zip present; layout test covers it")
    assert not EVAL_AIML_ZIP.exists()


@pytest.mark.skipif(not AIML_ZIP.exists(), reason="eval_aiml zip not built")
def test_eval_aiml_zip_layout() -> None:
    with ZipFile(AIML_ZIP) as archive:
        names = archive.namelist()
    for root in expected_roots():
        if root.endswith("/"):
            assert any(name.startswith(root) for name in names), root
        else:
            assert root in names, root
    assert any(name.startswith("packages/") and name.endswith(".whl") for name in names)
    assert any("node_modules/" in name for name in names)
    transformers = [name for name in names if name.startswith(TRANSFORMERS_ROOT)]
    assert len(transformers) >= 1000


@pytest.mark.skipif(
    os.environ.get("EVAL_AIML") != "1" or not AIML_ZIP.exists(),
    reason="set EVAL_AIML=1 after building the zip",
)
def test_eval_aiml_ingest_and_required_retrieve(tmp_path: Path) -> None:
    from material_platform.application.deep_research import DeepResearchService
    from material_platform.application.index import make_index_service
    from material_platform.infrastructure.database.engine import (
        make_engine,
        make_session_factory,
    )

    settings = _eval_settings(tmp_path / "data")
    run = ingest_and_process(AIML_ZIP, settings, process=True, strict=False)
    assert not ingest_errors(run), ingest_errors(run)
    assert not discovery_errors(run.ingest.materials)

    suite = make_suite()
    engine = make_engine(settings)
    sessions = make_session_factory(engine)
    index = make_index_service(settings)
    with sessions() as session:
        scored = score_suite(
            suite,
            DeepResearchService(session, index).select,
            modes=(LEXICAL,),
        )
    required = [item for item in scored.cases if item.case_id in REQUIRED_LEXICAL_IDS]
    missed = [item.case_id for item in required if not item.hit_at_1]
    assert not missed, format_report(scored)
    ok, total = hit_at_1(scored, LEXICAL)
    assert total >= len(REQUIRED_LEXICAL_IDS)
    assert ok >= len(REQUIRED_LEXICAL_IDS)
