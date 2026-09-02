from __future__ import annotations

from material_platform.agent.llm import named_llm
from material_platform.agent.models import (
    RAW_QUESTION_ID,
    QuestionState,
    ResearchPlan,
    ResearchQuestion,
)
from material_platform.agent.state import AgentState
from material_platform.agent.trace import Tracer
from material_platform.analysis.protocol import LlmClient


def plan_state(
    state: AgentState,
    *,
    tracer: Tracer,
    client: LlmClient | None = None,
) -> AgentState:
    with tracer.span("plan", query=state.query):
        plan = _llm_plan(
            state.query,
            named_llm(client, tracer, "plan"),
            limit=state.budgets.plan_questions,
        )
        if plan is None:
            plan = ResearchPlan(
                objective=state.query,
                questions=(
                    ResearchQuestion(id=RAW_QUESTION_ID, question=state.query),
                ),
            )
        plan = _ensure_raw(
            state.query, plan, limit=state.budgets.plan_questions
        )
        state.plan = plan
        state.questions = {
            item.id: QuestionState(question_id=item.id) for item in plan.questions
        }
        queued: list[tuple[str, str, bool]] = [
            (RAW_QUESTION_ID, state.query, False)
        ]
        for item in plan.questions:
            if item.id == RAW_QUESTION_ID:
                continue
            queued.append((item.id, item.question, False))
        state.queue = queued
        tracer.event("plan", questions=len(plan.questions), objective=plan.objective)
        tracer.set_output(
            {
                "objective": plan.objective,
                "questions": [
                    {"id": item.id, "question": item.question}
                    for item in plan.questions
                ],
            }
        )
    return state


def _ensure_raw(
    query: str, plan: ResearchPlan, *, limit: int
) -> ResearchPlan:
    questions = list(plan.questions[:limit])
    if not questions or questions[0].id != RAW_QUESTION_ID:
        questions.insert(
            0, ResearchQuestion(id=RAW_QUESTION_ID, question=query)
        )
    else:
        questions[0] = ResearchQuestion(id=RAW_QUESTION_ID, question=query)
    seen: set[str] = set()
    unique: list[ResearchQuestion] = []
    for item in questions:
        if item.id in seen:
            continue
        seen.add(item.id)
        unique.append(item)
    objective = plan.objective.strip() or query
    return ResearchPlan(
        objective=objective,
        questions=tuple(unique[: limit + 1]),
    )


def _llm_plan(
    query: str, client: LlmClient | None, *, limit: int
) -> ResearchPlan | None:
    if client is None:
        return None
    prompt = (
        f"Split this research request into at most {limit} concrete questions. "
        "Reply JSON: {\"objective\": str, \"questions\": "
        "[{\"id\": \"Q1\", \"question\": str, \"priority\": \"required\", "
        "\"comparative\": bool}]}\n\n"
        f"Request:\n{query}"
    )
    try:
        payload = client.complete_json(prompt)
    except Exception:
        return None
    raw_questions = payload.get("questions")
    if not isinstance(raw_questions, list):
        return None
    questions: list[ResearchQuestion] = []
    for index, item in enumerate(raw_questions, start=1):
        if not isinstance(item, dict):
            continue
        text = item.get("question")
        if not isinstance(text, str) or not text.strip():
            continue
        qid = item.get("id")
        if not isinstance(qid, str) or not qid.strip():
            qid = f"Q{index}"
        if qid == RAW_QUESTION_ID:
            qid = f"Q{index}"
        priority = item.get("priority")
        if priority not in {"required", "optional"}:
            priority = "required"
        questions.append(
            ResearchQuestion(
                id=qid.strip(),
                question=text.strip(),
                priority=priority,
                comparative=bool(item.get("comparative")),
            )
        )
        if len(questions) >= limit:
            break
    if not questions:
        return None
    objective = payload.get("objective")
    if not isinstance(objective, str) or not objective.strip():
        objective = query
    return ResearchPlan(objective=objective.strip(), questions=tuple(questions))
