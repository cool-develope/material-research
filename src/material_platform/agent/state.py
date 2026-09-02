from __future__ import annotations

from dataclasses import dataclass, field

from material_platform.agent.budgets import STANDARD, AgentBudgets
from material_platform.agent.models import (
    EvidenceItem,
    Finding,
    QuestionState,
    ResearchPlan,
    ResearchQuestion,
    ResearchReport,
    SearchAttempt,
)
from material_platform.domain.citation import Citation


@dataclass
class AgentState:
    query: str
    plan: ResearchPlan
    queue: list[tuple[str, str, bool]] = field(default_factory=list)
    evidence: list[EvidenceItem] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
    questions: dict[str, QuestionState] = field(default_factory=dict)
    history: list[SearchAttempt] = field(default_factory=list)
    pending: list[Citation] = field(default_factory=list)
    pending_question: str = ""
    select_calls: int = 0
    report: ResearchReport | None = None
    budgets: AgentBudgets = field(default_factory=lambda: STANDARD)


def empty_plan(query: str) -> ResearchPlan:
    question = ResearchQuestion(id="Q0", question=query)
    return ResearchPlan(objective=query, questions=(question,))


def bootstrap(query: str, budgets: AgentBudgets = STANDARD) -> AgentState:
    plan = empty_plan(query)
    state = AgentState(query=query, plan=plan, budgets=budgets)
    state.questions = {
        item.id: QuestionState(question_id=item.id) for item in plan.questions
    }
    state.queue = [(plan.questions[0].id, query, False)]
    return state
