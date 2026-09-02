from uuid import uuid4

import pytest

from material_platform.domain.citation import Citation
from material_platform.domain.research_material import ContentLocation
from material_platform.eval import EvalCase, ExpectedHit, SuiteScore, mrr, score_case
from material_platform.eval.experiment import (
    ExperimentRun,
    format_compare,
    parse_chunk_sweep,
)


def test_parse_chunk_sweep() -> None:
    assert parse_chunk_sweep("chunk_tokens=256,512,1024") == (256, 512, 1024)


def test_parse_chunk_sweep_rejects_other_knobs() -> None:
    with pytest.raises(ValueError, match="chunk_tokens"):
        parse_chunk_sweep("reranker=off,bge")


def test_format_compare_shows_units_and_mrr() -> None:
    miss = score_case(
        EvalCase(id="a", query="q", expect=(ExpectedHit(path="x"),)),
        lambda query, *, limit=5, material_type=None: (),
    )
    hit = score_case(
        EvalCase(id="b", query="q", expect=(ExpectedHit(path="paper.pdf", page=1),)),
        lambda query, *, limit=5, material_type=None: (
            Citation(
                material_id=uuid4(),
                title="t",
                location=ContentLocation(path="paper.pdf", page=1),
                citation="paper.pdf page 1",
                snippet="",
                score=1.0,
            ),
        ),
    )
    score = SuiteScore(suite_id="demo", cases=(hit, miss))
    assert mrr(score) == 0.5
    table = format_compare(
        (
            ExperimentRun(
                label="chunk_tokens=512",
                chunk_tokens=512,
                materials=3,
                units=8,
                score=score,
            ),
        )
    )
    assert "chunk_tokens=512" in table
    assert "8" in table
    assert "0.500" in table
