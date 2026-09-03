from pathlib import Path

from sqlalchemy.orm import Session
from tests.unit.discovery.trees import EVAL_HARD_ZIP, SIMPLE_ZIP
from tests.unit.helpers.eval_run import ingest_and_process

from material_platform.agent.service import ResearchAgent
from material_platform.application.deep_research import DeepResearchService
from material_platform.application.index import IndexService
from material_platform.eval import (
    HARD_SUITE,
    LEXICAL,
    hit_at_1,
    lexical_failed,
    load_suite,
    score_suite,
)
from material_platform.infrastructure.tracing.trace import RecordingTracer


def test_agent_simple_mix_handle_request(
    session: Session,
    tmp_path: Path,
    index: IndexService,
) -> None:
    ingest_and_process(session, tmp_path, SIMPLE_ZIP, index)
    tracer = RecordingTracer()
    agent = ResearchAgent(DeepResearchService(session, index).select, tracer=tracer)
    report = agent.ask("handle_request")
    assert agent.last_select_queries[0] == "handle_request"
    assert any("src/api.py" in item.citation for item in report.citations)
    assert all("__material__" not in item.citation for item in report.citations)
    assert "plan" in [span.name for span in tracer.spans]
    names = [span.name for span in tracer.spans]
    assert "retrieve" in names
    assert "embed" in names
    assert "hop1" in names
    assert "hop2" in names
    assert "rerank" in names
    assert "diversity" in names


def test_agent_eval_hard_lexical_hit_at_1(
    session: Session,
    tmp_path: Path,
    index: IndexService,
) -> None:
    ingest_and_process(session, tmp_path, EVAL_HARD_ZIP, index)
    scored = score_suite(
        load_suite(HARD_SUITE),
        DeepResearchService(session, index).select,
        modes=(LEXICAL,),
    )
    ok, total = hit_at_1(scored, LEXICAL)
    assert not lexical_failed(scored), scored
    assert (ok, total) == (4, 4)
