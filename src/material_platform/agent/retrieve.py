from __future__ import annotations

from collections.abc import Callable

from material_platform.agent.state import AgentState
from material_platform.domain.citation import Citation
from material_platform.domain.research import SearchAttempt
from material_platform.infrastructure.qdrant.payload import MATERIAL_UNIT_ID
from material_platform.infrastructure.tracing.trace import Tracer

SelectFn = Callable[..., tuple[Citation, ...]]


def retrieve_one(
    state: AgentState,
    select: SelectFn,
    *,
    tracer: Tracer,
) -> AgentState:
    if not state.queue or state.select_calls >= state.budgets.select_calls:
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
            for hit in select(query, limit=20, tracer=tracer)
            if hit.citation != MATERIAL_UNIT_ID and "__material__" not in hit.citation
        )
        with tracer.span("diversity", per_material=state.budgets.units_per_material):
            trimmed = _diversity(hits, per_material=state.budgets.units_per_material)
            tracer.set_output(
                {
                    "in": len(hits),
                    "kept": len(trimmed),
                    "selected": _trace_hits(trimmed),
                }
            )
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
                "top": trimmed[0].citation if trimmed else None,
                "materials": _trace_materials(trimmed),
                "selected": _trace_hits(trimmed),
            }
        )
    return state


def _diversity(
    hits: tuple[Citation, ...], *, per_material: int
) -> tuple[Citation, ...]:
    counts: dict[str, int] = {}
    kept: list[Citation] = []
    for hit in hits:
        key = str(hit.material_id)
        used = counts.get(key, 0)
        if used >= per_material:
            continue
        counts[key] = used + 1
        kept.append(hit)
    return tuple(kept)


def _trace_hits(hits: tuple[Citation, ...]) -> list[dict[str, object]]:
    return [
        {
            "citation": hit.citation,
            "title": hit.title,
            "material_id": str(hit.material_id),
            "score": round(hit.score, 4),
        }
        for hit in hits
    ]


def _trace_materials(hits: tuple[Citation, ...]) -> list[dict[str, str]]:
    seen: set[str] = set()
    materials: list[dict[str, str]] = []
    for hit in hits:
        key = str(hit.material_id)
        if key in seen:
            continue
        seen.add(key)
        materials.append({"material_id": key, "title": hit.title})
    return materials
