from __future__ import annotations

from pathlib import Path
from typing import Final, Literal

from material_platform.domain.base import Contract

Mode = Literal["lexical", "semantic"]
LEXICAL: Final[Mode] = "lexical"
SEMANTIC: Final[Mode] = "semantic"

_REPO = Path(__file__).resolve().parents[3]
DEFAULT_SUITE = _REPO / "tests" / "fixtures" / "eval" / "simple_mix.json"
HARD_SUITE = _REPO / "tests" / "fixtures" / "eval" / "eval_hard.json"


class ExpectedHit(Contract):
    path: str
    page: int | None = None
    lines: bool = False
    section: str | None = None


class EvalCase(Contract):
    id: str
    query: str
    mode: Mode = LEXICAL
    k: int = 5
    material_type: str | None = None
    expect: tuple[ExpectedHit, ...]


class EvalSuite(Contract):
    id: str
    cases: tuple[EvalCase, ...]


def load_suite(path: Path) -> EvalSuite:
    return EvalSuite.model_validate_json(path.read_text(encoding="utf-8"))
