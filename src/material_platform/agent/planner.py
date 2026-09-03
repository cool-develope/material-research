from __future__ import annotations

from material_platform.agent.compact import standalone_question
from material_platform.agent.context import for_plan
from material_platform.agent.llm import named_llm
from material_platform.agent.models import (
    QuestionState,
    ResearchPlan,
    ResearchQuestion,
    ResearchRequest,
    ResearchScope,
)
from material_platform.agent.state import AgentState
from material_platform.agent.trace import Tracer
from material_platform.analysis.protocol import LlmClient

_PLAN_MARK = "You are the planner for a Deep Research system."


def plan_state(
    state: AgentState,
    *,
    tracer: Tracer,
    client: LlmClient | None = None,
) -> AgentState:
    with tracer.span("plan", query=state.query):
        working = for_plan(state)
        tracer.set_input(working)
        plan = _llm_plan(
            named_llm(client, tracer, "plan"),
            limit=state.budgets.plan_questions,
            working=working,
            latest=state.query,
        )
        if plan is None:
            plan = _fallback_plan(state)
        plan = _trim(plan, limit=state.budgets.plan_questions)
        state.request = ResearchRequest(objective=plan.objective)
        state.plan = plan
        state.questions = {
            item.id: QuestionState(question_id=item.id) for item in plan.questions
        }
        if plan.needs_retrieval and plan.questions:
            state.queue = [(item.id, item.question, False) for item in plan.questions]
        else:
            if not plan.needs_retrieval and state.prior_plan is not None:
                plan = plan.model_copy(update={"questions": state.prior_plan.questions})
                state.plan = plan
                state.questions = {
                    item.id: QuestionState(question_id=item.id)
                    for item in plan.questions
                }
            elif not plan.questions and state.prior_plan is not None:
                plan = plan.model_copy(update={"questions": state.prior_plan.questions})
                state.plan = plan
                state.questions = {
                    item.id: QuestionState(question_id=item.id)
                    for item in plan.questions
                }
            if not plan.needs_retrieval:
                state.evidence = list(state.prior_evidence)
                state.findings = list(state.prior_findings)
            state.queue = []
        tracer.event(
            "plan",
            questions=len(plan.questions),
            objective=plan.objective,
            intent=plan.intent,
            needs_retrieval=plan.needs_retrieval,
        )
        tracer.set_output(
            {
                "intent": plan.intent,
                "objective": plan.objective,
                "needs_retrieval": plan.needs_retrieval,
                "questions": [
                    {"id": item.id, "question": item.question}
                    for item in plan.questions
                ],
            }
        )
    return state


def _fallback_plan(state: AgentState) -> ResearchPlan:
    question = standalone_question(state.query, state.conversation)
    return ResearchPlan(
        objective=question,
        intent="research",
        needs_retrieval=True,
        questions=(ResearchQuestion(id="Q1", question=question),),
    )


def _trim(plan: ResearchPlan, *, limit: int) -> ResearchPlan:
    seen: set[str] = set()
    unique: list[ResearchQuestion] = []
    for item in plan.questions:
        qid = item.id.strip() or f"Q{len(unique) + 1}"
        if qid in seen:
            continue
        seen.add(qid)
        unique.append(item.model_copy(update={"id": qid}))
        if len(unique) >= limit:
            break
    return plan.model_copy(update={"questions": tuple(unique)})


def _llm_plan(
    client: LlmClient | None,
    *,
    limit: int,
    working: str,
    latest: str,
) -> ResearchPlan | None:
    if client is None:
        return None
    prompt = (
        f"{_PLAN_MARK}\n"
        "Use the thread and the latest user message to decide what the user "
        "currently wants. The latest user request has priority. "
        "Do not continue the thread as a chat assistant.\n"
        f"Generate at most {limit} research questions for the current request. "
        "Questions must be understandable without the thread.\n\n"
        f"{working}\n\n"
        'Reply with one JSON object only: {"intent": str, "objective": str, '
        '"scope": {"materials": [str], "exclude_topics": [str]}, '
        '"questions": [{"id": "Q1", "question": str, "priority": "required", '
        '"comparative": false}], "needs_retrieval": true}'
    )
    try:
        payload = client.complete_json(prompt)
    except Exception:
        return None
    questions = _questions(payload.get("questions"), limit=limit)
    objective = payload.get("objective")
    if not isinstance(objective, str) or not objective.strip():
        objective = latest
    intent = payload.get("intent")
    if not isinstance(intent, str) or not intent.strip():
        intent = "research"
    needs = payload.get("needs_retrieval")
    if not isinstance(needs, bool):
        needs = intent.strip().lower() not in {"rewrite", "summarize", "summarise"}
    if not questions and needs:
        return None
    return ResearchPlan(
        objective=objective.strip(),
        intent=intent.strip(),
        needs_retrieval=needs,
        questions=tuple(questions),
        scope=_scope(payload.get("scope")),
    )


def _questions(raw: object, *, limit: int) -> list[ResearchQuestion]:
    if not isinstance(raw, list):
        return []
    questions: list[ResearchQuestion] = []
    for index, item in enumerate(raw, start=1):
        text = ""
        qid = f"Q{index}"
        priority = "required"
        comparative = False
        if isinstance(item, str) and item.strip():
            text = item.strip()
        elif isinstance(item, dict):
            value = item.get("question")
            if isinstance(value, str) and value.strip():
                text = value.strip()
            ident = item.get("id")
            if isinstance(ident, str) and ident.strip():
                qid = ident.strip()
            if item.get("priority") in {"required", "optional"}:
                priority = str(item.get("priority"))
            comparative = bool(item.get("comparative"))
        if not text:
            continue
        questions.append(
            ResearchQuestion(
                id=qid,
                question=text,
                priority=priority,  # type: ignore[arg-type]
                comparative=comparative,
            )
        )
        if len(questions) >= limit:
            break
    return questions


def _scope(raw: object) -> ResearchScope:
    if not isinstance(raw, dict):
        return ResearchScope()
    return ResearchScope(
        materials=_string_tuple(raw.get("materials")),
        exclude_topics=_string_tuple(raw.get("exclude_topics")),
    )


def _string_tuple(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(
        item.strip() for item in value if isinstance(item, str) and item.strip()
    )
