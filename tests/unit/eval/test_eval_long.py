from pathlib import Path

from sqlalchemy.orm import Session
from tests.unit.discovery.trees import EVAL_LONG_ZIP
from tests.unit.helpers.eval_run import ingest_and_process

from material_platform.application.deep_research import DeepResearchService
from material_platform.application.index import IndexService
from material_platform.config import Settings
from material_platform.eval import (
    LEXICAL,
    LONG_SUITE,
    hit_at_1,
    lexical_failed,
    load_suite,
    score_suite,
)
from material_platform.eval.experiment import run_chunk_sweep


def test_eval_long_lexical_cases_hit_at_1(
    session: Session,
    tmp_path: Path,
    index: IndexService,
) -> None:
    ingest_and_process(session, tmp_path, EVAL_LONG_ZIP, index)
    suite = load_suite(LONG_SUITE)
    scored = score_suite(
        suite,
        DeepResearchService(session, index).select,
        modes=(LEXICAL,),
    )
    ok, total = hit_at_1(scored, LEXICAL)
    assert not lexical_failed(scored), scored
    assert (ok, total) == (3, 3)


def test_eval_long_chunk_sweep_changes_unit_count(tmp_path: Path) -> None:
    runs = run_chunk_sweep(
        EVAL_LONG_ZIP,
        load_suite(LONG_SUITE),
        (256, 1024),
        work_dir=tmp_path / "sweep",
        settings=Settings(_env_file=None),
        lexical_only=True,
    )
    assert runs[0].units > runs[1].units
    assert runs[0].materials == runs[1].materials
    assert not lexical_failed(runs[0].score)
    assert not lexical_failed(runs[1].score)
