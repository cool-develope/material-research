from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from material_platform.domain.base import Contract
from material_platform.domain.citation import Citation
from material_platform.eval.cases import (
    LEXICAL,
    SEMANTIC,
    EvalCase,
    EvalSuite,
    ExpectedHit,
    Mode,
)


class SelectFn(Protocol):
    def __call__(
        self,
        query: str,
        *,
        limit: int = 5,
        material_type: str | None = None,
    ) -> tuple[Citation, ...]: ...


class CaseScore(Contract):
    case_id: str
    mode: Mode
    query: str
    k: int
    hit_at_1: bool
    recall_at_k: float
    citations: tuple[str, ...]


class SuiteScore(Contract):
    suite_id: str
    cases: tuple[CaseScore, ...]


def matches(citation: Citation, expected: ExpectedHit) -> bool:
    haystack = f"{citation.location.path or ''} {citation.citation}"
    if expected.path not in haystack:
        return False
    if expected.page is not None and citation.location.page != expected.page:
        return False
    if expected.lines and citation.location.line_start is None:
        return False
    if (
        expected.section is not None
        and citation.location.section != expected.section
    ):
        return False
    return True


def score_case(case: EvalCase, select: SelectFn) -> CaseScore:
    citations = select(
        case.query, limit=case.k, material_type=case.material_type
    )
    top = citations[: case.k]
    found = sum(
        1
        for expected in case.expect
        if any(matches(hit, expected) for hit in top)
    )
    hit_at_1 = bool(citations) and any(
        matches(citations[0], expected) for expected in case.expect
    )
    total = len(case.expect)
    return CaseScore(
        case_id=case.id,
        mode=case.mode,
        query=case.query,
        k=case.k,
        hit_at_1=hit_at_1,
        recall_at_k=(found / total) if total else 0.0,
        citations=tuple(hit.citation for hit in top),
    )


def score_suite(
    suite: EvalSuite,
    select: SelectFn,
    *,
    modes: Sequence[Mode] | None = None,
) -> SuiteScore:
    allowed = frozenset(modes) if modes is not None else None
    cases = tuple(
        score_case(case, select)
        for case in suite.cases
        if allowed is None or case.mode in allowed
    )
    return SuiteScore(suite_id=suite.id, cases=cases)


def hit_at_1(score: SuiteScore, mode: Mode) -> tuple[int, int]:
    items = [item for item in score.cases if item.mode == mode]
    return sum(1 for item in items if item.hit_at_1), len(items)


def lexical_failed(score: SuiteScore) -> tuple[CaseScore, ...]:
    return tuple(
        item
        for item in score.cases
        if item.mode == LEXICAL and not item.hit_at_1
    )


def format_report(score: SuiteScore) -> str:
    lex_ok, lex_n = hit_at_1(score, LEXICAL)
    sem_ok, sem_n = hit_at_1(score, SEMANTIC)
    lines = [
        f"{score.suite_id}  lexical {lex_ok}/{lex_n} hit@1  "
        f"semantic {sem_ok}/{sem_n} hit@1",
        "",
    ]
    for item in score.cases:
        mark = "ok" if item.hit_at_1 else "--"
        got = item.citations[0] if item.citations else "(none)"
        extra = f"  ({item.mode})" if item.mode != LEXICAL else ""
        lines.append(f"  {mark}  {item.case_id}{extra}  {got}")
    return "\n".join(lines) + "\n"
