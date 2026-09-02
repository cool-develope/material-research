from __future__ import annotations

from material_platform.agent.llm import named_llm
from material_platform.agent.models import (
    MAX_SELECT_CALLS,
    RAW_QUESTION_ID,
    QuestionState,
)
from material_platform.agent.state import AgentState
from material_platform.agent.trace import Tracer
from material_platform.analysis.protocol import LlmClient


def cover_state(state: AgentState, *, tracer: Tracer) -> AgentState:
    with tracer.span("cover", select_calls=state.select_calls):
        material_count = len({item.material_id for item in state.evidence})
        for question in state.plan.questions:
            rows = [
                item for item in state.evidence if item.question_id == question.id
            ]
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
                "status": {
                    qid: row.status for qid, row in state.questions.items()
                },
            }
        )
    return state


def follow_up_state(
    state: AgentState, *, tracer: Tracer, client: LlmClient | None = None
) -> AgentState:
    gap = _next_gap(state)
    if gap is None:
        return state
    question = next(item for item in state.plan.questions if item.id == gap)
    extra = _follow_up_query(question.question, state)
    drafted = _llm_follow_up(
        question.question, extra, named_llm(client, tracer, "follow_up")
    )
    if drafted:
        extra = drafted
    seen = {attempt.query for attempt in state.history}
    if extra in seen or extra == question.question:
        state.questions[gap] = state.questions[gap].model_copy(
            update={"status": "unresolved"}
        )
        return state
    with tracer.span("follow_up", question_id=gap, query=extra):
        state.queue.append((gap, extra, True))
        tracer.event("follow_up", question_id=gap, query=extra)
        tracer.set_output({"question_id": gap, "query": extra})
    return state


def has_work(state: AgentState) -> bool:
    return bool(state.queue) and state.select_calls < MAX_SELECT_CALLS


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


def _next_gap(state: AgentState) -> str | None:
    for question in state.plan.questions:
        row = state.questions[question.id]
        if row.status == "gap" and row.iterations < 2:
            if question.id == RAW_QUESTION_ID and row.iterations >= 1:
                continue
            return question.id
    return None


def _follow_up_query(question: str, state: AgentState) -> str:
    tokens = [part for part in question.split() if len(part) > 3][:8]
    seen = " ".join(
        sorted(
            {
                item.citation.location.path or ""
                for item in state.evidence
                if item.citation.location.path
            }
        )[:4]
    )
    return " ".join(tokens + (["evidence", seen] if seen else ["evidence"]))


def _llm_follow_up(
    question: str, draft: str, client: LlmClient | None
) -> str | None:
    if client is None:
        return None
    prompt = (
        "One short follow-up search query for this unanswered question. "
        "JSON {\"query\": str}. Do not repeat the original question.\n\n"
        f"Question: {question}\nDraft: {draft}"
    )
    try:
        payload = client.complete_json(prompt)
    except Exception:
        return None
    text = payload.get("query")
    if isinstance(text, str) and text.strip() and text.strip() != question:
        return text.strip()
    return None
