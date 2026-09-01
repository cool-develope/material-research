from pathlib import Path

from sqlalchemy.orm import Session
from tests.unit.discovery.trees import EVAL_HARD_ZIP
from tests.unit.helpers.eval_run import ingest_and_process

from material_platform.application.deep_research import DeepResearchService
from material_platform.eval import (
    HARD_SUITE,
    LEXICAL,
    hit_at_1,
    lexical_failed,
    load_suite,
    score_suite,
)
from material_platform.index import IndexService


def test_eval_hard_lexical_cases_hit_at_1(
    session: Session,
    tmp_path: Path,
    index: IndexService,
) -> None:
    ingest_and_process(session, tmp_path, EVAL_HARD_ZIP, index)
    suite = load_suite(HARD_SUITE)
    scored = score_suite(
        suite,
        DeepResearchService(session, index).select,
        modes=(LEXICAL,),
    )
    ok, total = hit_at_1(scored, LEXICAL)
    assert not lexical_failed(scored), scored
    assert (ok, total) == (4, 4)
