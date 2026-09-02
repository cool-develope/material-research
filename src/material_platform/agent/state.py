from __future__ import annotations

from dataclasses import dataclass, field

from material_platform.agent.budgets import STANDARD, AgentBudgets
from material_platform.agent.compact import clip_answer, fold_turns, make_request
from material_platform.agent.models import (
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
from material_platform.analysis.protocol import LlmClient
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
    conversation: list[ChatTurn] = field(default_factory=list)
    request: ResearchRequest | None = None
    summary: ConversationSummary | None = None
    recalled: str = ""


def empty_plan(query: str) -> ResearchPlan:
    question = ResearchQuestion(id="Q0", question=query)
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
    request = make_request(query, summary, recent, previous.request, client=client)
    state = bootstrap(query, budgets)
    state.conversation = recent
    state.summary = summary
    state.request = request
    return state
