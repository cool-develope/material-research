from __future__ import annotations

from dataclasses import dataclass, field

from material_platform.agent.compact import (
    clip_answer,
    clip_research,
    fold_turns,
)
from material_platform.domain.budgets import STANDARD, AgentBudgets
from material_platform.domain.citation import Citation
from material_platform.domain.protocols import LlmClient
from material_platform.domain.research import (
    ChatTurn,
    ConversationSummary,
    EvidenceItem,
    Finding,
    QuestionState,
    ResearchPlan,
    ResearchQuestion,
    ResearchReport,
    ResearchRequest,
    SearchAttempt,
)


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
    conversation: list[ChatTurn] = field(default_factory=list)
    request: ResearchRequest | None = None
    summary: ConversationSummary | None = None
    prior_research: str = ""
    prior_findings: list[Finding] = field(default_factory=list)
    prior_evidence: list[EvidenceItem] = field(default_factory=list)
    prior_plan: ResearchPlan | None = None


def empty_plan(query: str) -> ResearchPlan:
    question = ResearchQuestion(id="Q1", question=query)
    return ResearchPlan(objective=query, questions=(question,))


def bootstrap(query: str, budgets: AgentBudgets = STANDARD) -> AgentState:
    plan = empty_plan(query)
    state = AgentState(query=query, plan=plan, budgets=budgets)
    state.request = ResearchRequest(objective=query)
    state.questions = {
        item.id: QuestionState(question_id=item.id) for item in plan.questions
    }
    state.queue = [(plan.questions[0].id, query, False)]
    return state


def continue_state(
    previous: AgentState,
    query: str,
    budgets: AgentBudgets = STANDARD,
    *,
    client: LlmClient | None = None,
) -> AgentState:
    turns = list(previous.conversation)
    answer = ""
    if previous.report is not None:
        answer = previous.report.summary.strip() or previous.report.text
    turns.append(ChatTurn(query=previous.query, answer=clip_answer(answer)))
    recent, summary = fold_turns(previous.summary, turns, client=client)
    state = bootstrap(query, budgets)
    state.conversation = recent
    state.summary = summary
    state.prior_plan = previous.plan
    state.prior_findings = list(previous.findings)
    state.prior_evidence = list(previous.evidence)
    state.prior_research = _prior_research(previous)
    state.queue = []
    return state


def state_from_turns(
    turns: list[ChatTurn], budgets: AgentBudgets = STANDARD
) -> AgentState | None:
    if not turns:
        return None
    last = turns[-1]
    previous = bootstrap(last.query, budgets)
    previous.conversation = list(turns[:-1])
    previous.request = ResearchRequest(objective=last.query)
    previous.report = ResearchReport(
        objective=last.query,
        sections=(),
        summary=last.answer,
        citations=(),
        text=last.answer,
    )
    previous.prior_research = clip_research(last.answer)
    return previous


def _prior_research(previous: AgentState) -> str:
    if previous.report is not None:
        text = previous.report.summary.strip() or previous.report.objective
        return clip_research(text)
    if previous.findings:
        return clip_research("; ".join(item.claim for item in previous.findings[:4]))
    return previous.prior_research
