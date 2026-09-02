from uuid import uuid4

from material_platform.domain.citation import Citation
from material_platform.domain.research_material import ContentLocation
from material_platform.eval import (
    AIML_SUITE,
    DEFAULT_SUITE,
    HARD_SUITE,
    LEXICAL,
    LONG_SUITE,
    SEMANTIC,
    EvalCase,
    ExpectedHit,
    format_report,
    hit_at_1,
    lexical_failed,
    load_suite,
    matches,
    score_case,
    score_suite,
)


def _citation(
    path: str,
    *,
    page: int | None = None,
    line_start: int | None = None,
    line_end: int | None = None,
) -> Citation:
    location = ContentLocation(
        path=path, page=page, line_start=line_start, line_end=line_end
    )
    if page is not None:
        text = f"{path} page {page}"
    elif line_start is not None and line_end is not None:
        text = f"{path} lines {line_start}-{line_end}"
    else:
        text = path
    return Citation(
        material_id=uuid4(),
        title="t",
        location=location,
        citation=text,
        snippet="",
        score=1.0,
    )


def test_matches_path_and_page() -> None:
    hit = _citation("paper.pdf", page=1)
    assert matches(hit, ExpectedHit(path="paper.pdf", page=1))
    assert not matches(hit, ExpectedHit(path="paper.pdf", page=2))
    assert not matches(hit, ExpectedHit(path="src/api.py", page=1))


def test_matches_requires_line_range_when_asked() -> None:
    lines = _citation("src/api.py", line_start=1, line_end=2)
    page = _citation("src/api.py", page=1)
    assert matches(lines, ExpectedHit(path="src/api.py", lines=True))
    assert not matches(page, ExpectedHit(path="src/api.py", lines=True))
    assert matches(page, ExpectedHit(path="src/api.py"))


def test_matches_section() -> None:
    hit = Citation(
        material_id=uuid4(),
        title="t",
        location=ContentLocation(
            path="src/api.py", line_start=1, line_end=2, section="retry_failed_request"
        ),
        citation="src/api.py lines 1-2",
        snippet="",
        score=1.0,
    )
    assert matches(
        hit, ExpectedHit(path="src/api.py", section="retry_failed_request")
    )
    assert not matches(
        hit, ExpectedHit(path="src/api.py", section="handle_request")
    )


def test_load_default_suite() -> None:
    suite = load_suite(DEFAULT_SUITE)
    assert suite.id == "simple_mix"
    modes = {case.mode for case in suite.cases}
    assert LEXICAL in modes
    assert SEMANTIC in modes
    assert all(case.expect for case in suite.cases)


def test_load_hard_suite() -> None:
    suite = load_suite(HARD_SUITE)
    assert suite.id == "eval_hard"
    assert sum(1 for case in suite.cases if case.mode == LEXICAL) == 4
    assert sum(1 for case in suite.cases if case.mode == SEMANTIC) == 3


def test_load_long_suite() -> None:
    suite = load_suite(LONG_SUITE)
    assert suite.id == "eval_long"
    assert all(case.mode == LEXICAL for case in suite.cases)
    assert len(suite.cases) == 3


def test_load_aiml_suite() -> None:
    suite = load_suite(AIML_SUITE)
    assert suite.id == "eval_aiml"
    assert sum(1 for case in suite.cases if case.mode == LEXICAL) == 10
    assert sum(1 for case in suite.cases if case.mode == SEMANTIC) == 2


def test_score_case_hit_at_1() -> None:
    case = EvalCase(
        id="api",
        query="handle_request",
        expect=(ExpectedHit(path="src/api.py", lines=True),),
    )

    def select(
        query: str,
        *,
        limit: int = 5,
        material_type: str | None = None,
    ) -> tuple[Citation, ...]:
        assert query == "handle_request"
        assert limit == 5
        assert material_type is None
        return (
            _citation("src/api.py", line_start=1, line_end=2),
            _citation("paper.pdf", page=1),
        )

    scored = score_case(case, select)
    assert scored.hit_at_1
    assert scored.rank == 1
    assert scored.recall_at_k == 1.0


def test_score_case_records_rank_when_not_first() -> None:
    case = EvalCase(
        id="api",
        query="handle_request",
        expect=(ExpectedHit(path="src/api.py", lines=True),),
    )

    def select(
        query: str,
        *,
        limit: int = 5,
        material_type: str | None = None,
    ) -> tuple[Citation, ...]:
        return (
            _citation("paper.pdf", page=1),
            _citation("src/api.py", line_start=1, line_end=2),
        )

    scored = score_case(case, select)
    assert not scored.hit_at_1
    assert scored.rank == 2
    assert scored.recall_at_k == 1.0


def test_score_suite_lexical_only_and_report() -> None:
    suite = load_suite(DEFAULT_SUITE)
    api = _citation("src/api.py", line_start=1, line_end=2)
    paper = _citation("paper.pdf", page=1)
    main = _citation("src/main.py", line_start=1, line_end=1)

    def select(
        query: str,
        *,
        limit: int = 5,
        material_type: str | None = None,
    ) -> tuple[Citation, ...]:
        if "handle_request" in query or "handler" in query:
            return (api,)
        if "print" in query:
            return (main,)
        return (paper,)

    lexical = score_suite(suite, select, modes=(LEXICAL,))
    ok, total = hit_at_1(lexical, LEXICAL)
    assert (ok, total) == (3, 3)
    assert not lexical_failed(lexical)
    report = format_report(lexical)
    assert "lexical 3/3 hit@1" in report
    assert "ok  paper-intro" in report

    missed = score_suite(
        suite,
        lambda query, *, limit=5, material_type=None: (paper,),
        modes=(LEXICAL,),
    )
    assert lexical_failed(missed)
    assert "lexical 1/3 hit@1" in format_report(missed)
