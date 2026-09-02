from __future__ import annotations

from collections.abc import Callable

from material_platform.agent.models import (
    MAX_SELECT_CALLS,
    MAX_UNITS_PER_MATERIAL,
    SearchAttempt,
)
from material_platform.agent.state import AgentState
from material_platform.agent.trace import Tracer
from material_platform.domain.citation import Citation
from material_platform.index.payload import MATERIAL_UNIT_ID

SelectFn = Callable[..., tuple[Citation, ...]]


def retrieve_one(
    state: AgentState,
    select: SelectFn,
    *,
    tracer: Tracer,
) -> AgentState:
    if not state.queue or state.select_calls >= MAX_SELECT_CALLS:
        state.pending = []
        state.pending_question = ""
        return state
    question_id, query, follow_up = state.queue.pop(0)
    with tracer.span(
        "retrieve",
        question_id=question_id,
        query=query,
        follow_up=follow_up,
        call=state.select_calls + 1,
    ):
        state.select_calls += 1
        hits = tuple(
            hit
            for hit in select(query, limit=20)
            if hit.citation != MATERIAL_UNIT_ID
            and "__material__" not in hit.citation
        )
        trimmed = _diversity(hits)
        state.pending = list(trimmed)
        state.pending_question = question_id
        current = state.questions[question_id]
        state.questions[question_id] = current.model_copy(
            update={
                "status": "researching",
                "iterations": current.iterations + 1,
                "last_query": query,
            }
        )
        state.history.append(
            SearchAttempt(
                query=query,
                question_id=question_id,
                hits=len(trimmed),
                follow_up=follow_up,
            )
        )
        tracer.event(
            "select",
            question_id=question_id,
            query=query,
            hits=len(trimmed),
            call=state.select_calls,
            follow_up=follow_up,
        )
        tracer.set_output(
            {
                "question_id": question_id,
                "hits": len(trimmed),
                "citations": [hit.citation for hit in trimmed],
            }
        )
    return state


def _diversity(hits: tuple[Citation, ...]) -> tuple[Citation, ...]:
    counts: dict[str, int] = {}
    kept: list[Citation] = []
    for hit in hits:
        key = str(hit.material_id)
        used = counts.get(key, 0)
        if used >= MAX_UNITS_PER_MATERIAL:
            continue
        counts[key] = used + 1
        kept.append(hit)
    return tuple(kept)
