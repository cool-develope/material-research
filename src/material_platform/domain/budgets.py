from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

AgentMode = Literal["quick", "standard", "deep"]


@dataclass(frozen=True)
class AgentBudgets:
    mode: AgentMode
    plan_questions: int
    select_calls: int
    units_per_material: int
    evidence_per_question: int
    evidence_total: int


QUICK = AgentBudgets(
    mode="quick",
    plan_questions=2,
    select_calls=3,
    units_per_material=3,
    evidence_per_question=8,
    evidence_total=24,
)
STANDARD = AgentBudgets(
    mode="standard",
    plan_questions=6,
    select_calls=8,
    units_per_material=5,
    evidence_per_question=20,
    evidence_total=80,
)
MAX_SELECT_CALLS = STANDARD.select_calls
DEEP = AgentBudgets(
    mode="deep",
    plan_questions=8,
    select_calls=16,
    units_per_material=5,
    evidence_per_question=20,
    evidence_total=160,
)
_MODES = {"quick": QUICK, "standard": STANDARD, "deep": DEEP}


def budgets_for(mode: str | None = None) -> AgentBudgets:
    key = (mode or "standard").strip().lower() or "standard"
    found = _MODES.get(key)
    if found is None:
        raise ValueError(f"unknown agent mode: {mode}")
    return found
