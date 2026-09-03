from __future__ import annotations

from material_platform.agent.context import for_gap
from material_platform.agent.llm import named_llm
from material_platform.agent.models import QuestionState
from material_platform.agent.state import AgentState
from material_platform.agent.trace import Tracer
from material_platform.analysis.protocol import LlmClient


def cover_state(state: AgentState, *, tracer: Tracer) -> AgentState:
    with tracer.span("cover", select_calls=state.select_calls):
        material_count = len({item.material_id for item in state.evidence})
        for question in state.plan.questions:
            rows = [item for item in state.evidence if item.question_id == question.id]
            current = state.questions[question.id]
            materials = tuple(dict.fromkeys(item.material_id for item in rows))
            evidence_ids = tuple(item.evidence_id for item in rows)
            status = _status(question.comparative, current, rows, material_count)
            state.questions[question.id] = current.model_copy(
                update={
                    "status": status,
                    "evidence_ids": evidence_ids,
                    "material_ids": materials,
                }
            )
        covered = sum(
            1 for item in state.questions.values() if item.status == "covered"
        )
        gaps = sum(1 for item in state.questions.values() if item.status == "gap")
        tracer.event("cover", covered=covered, gaps=gaps)
        tracer.set_output(
            {
                "covered": covered,
                "gaps": gaps,
                "status": {qid: row.status for qid, row in state.questions.items()},
            }
        )
    return state


def gap_check(
    state: AgentState, *, tracer: Tracer, client: LlmClient | None = None
) -> AgentState:
    cover_state(state, tracer=tracer)
    if state.queue or remaining_calls(state) <= 0:
        return state
    with tracer.span("gap", select_calls=state.select_calls):
        extras = _llm_gap(state, named_llm(client, tracer, "gap"))
        seen = {attempt.query for attempt in state.history}
        added: list[str] = []
        for question_id, query in extras:
            if remaining_calls(state) <= 0:
                break
            if not query or query in seen:
                continue
            state.queue.append((question_id, query, True))
            seen.add(query)
            added.append(query)
            tracer.event("gap", question_id=question_id, query=query)
        tracer.set_output({"answered": not added, "missing": added})
    return state


def has_work(state: AgentState) -> bool:
    return bool(state.queue) and state.select_calls < state.budgets.select_calls


def remaining_calls(state: AgentState) -> int:
    used = state.select_calls + len(state.queue)
    return max(0, state.budgets.select_calls - used)


def needs_retrieve(state: AgentState) -> bool:
    return state.plan.needs_retrieval and has_work(state)


def _status(
    comparative: bool,
    current: QuestionState,
    rows: list,
    material_count: int,
) -> str:
    if rows:
        if comparative and len({item.material_id for item in rows}) < 2:
            if material_count > 1 and current.iterations < 2:
                return "gap"
        return "covered"
    if current.iterations == 0:
        return "pending"
    if current.iterations < 2:
        return "gap"
    return "unresolved"


def _llm_gap(
    state: AgentState, client: LlmClient | None
) -> list[tuple[str, str]]:
    if client is None:
        return []
    prompt = (
        "Check whether the current findings answer the latest user request. "
        "If important information is missing and another search would help, "
        "list short search queries. Do not continue the thread.\n\n"
        f"{for_gap(state)}\n\n"
        'Reply with one JSON object only: {"answered": true, "missing": []}'
    )
    try:
        payload = client.complete_json(prompt)
    except Exception:
        return []
    if payload.get("answered") is True:
        return []
    raw = payload.get("missing")
    if not isinstance(raw, list):
        return []
    fallback = next(
        (
            question.id
            for question in state.plan.questions
            if state.questions.get(question.id)
            and state.questions[question.id].status in {"gap", "unresolved"}
        ),
        state.plan.questions[0].id if state.plan.questions else "Q1",
    )
    extras: list[tuple[str, str]] = []
    for item in raw:
        if isinstance(item, str) and item.strip():
            extras.append((fallback, item.strip()))
        elif isinstance(item, dict):
            query = item.get("query")
            if not isinstance(query, str) or not query.strip():
                continue
            qid = item.get("question_id")
            if not isinstance(qid, str) or qid not in state.questions:
                qid = fallback
            extras.append((qid, query.strip()))
    return extras
