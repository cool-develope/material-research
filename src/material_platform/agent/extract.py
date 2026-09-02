from __future__ import annotations

from material_platform.agent.llm import named_llm
from material_platform.agent.models import EvidenceItem
from material_platform.agent.state import AgentState
from material_platform.agent.trace import Tracer, clip
from material_platform.analysis.protocol import LlmClient
from material_platform.domain.citation import Citation


def extract_pending(
    state: AgentState,
    *,
    tracer: Tracer,
    client: LlmClient | None = None,
) -> AgentState:
    if not state.pending:
        return state
    question_id = state.pending_question
    with tracer.span("extract", question_id=question_id, hits=len(state.pending)):
        items = _llm_items(
            question_id, state.pending, named_llm(client, tracer, "extract")
        )
        if items is None:
            items = tuple(
                _from_citation(question_id, hit, index)
                for index, hit in enumerate(state.pending, start=1)
            )
        existing = [
            item for item in state.evidence if item.question_id == question_id
        ]
        room = state.budgets.evidence_per_question - len(existing)
        global_room = state.budgets.evidence_total - len(state.evidence)
        take = min(room, global_room, len(items))
        state.evidence.extend(items[:take])
        state.pending = []
        tracer.event("extract", question_id=question_id, added=take)
        tracer.set_output(
            {
                "question_id": question_id,
                "added": take,
                "findings": [
                    {
                        "finding": clip(item.finding),
                        "stance": item.stance,
                        "citation": item.citation.citation,
                    }
                    for item in items[:take]
                ],
            }
        )
    return state


def _from_citation(question_id: str, hit: Citation, index: int) -> EvidenceItem:
    return EvidenceItem(
        evidence_id=f"{question_id}-E{index}-{hit.citation}",
        question_id=question_id,
        material_id=hit.material_id,
        finding=hit.snippet or hit.citation,
        stance="supports",
        citation=hit,
    )


def _llm_items(
    question_id: str,
    hits: list[Citation],
    client: LlmClient | None,
) -> tuple[EvidenceItem, ...] | None:
    if client is None:
        return None
    lines = []
    for index, hit in enumerate(hits, start=1):
        lines.append(f"{index}. {hit.citation} :: {hit.snippet}")
    prompt = (
        "Extract evidence JSON {\"items\": [{\"index\": int, \"finding\": str, "
        "\"stance\": \"supports|contradicts|neutral\"}]}. "
        "index refers to the numbered citations. Do not invent locators.\n\n"
        + "\n".join(lines)
    )
    try:
        payload = client.complete_json(prompt)
    except Exception:
        return None
    raw = payload.get("items")
    if not isinstance(raw, list):
        return None
    items: list[EvidenceItem] = []
    for row in raw:
        if not isinstance(row, dict):
            continue
        index = row.get("index")
        finding = row.get("finding")
        if not isinstance(index, int) or not isinstance(finding, str):
            continue
        if index < 1 or index > len(hits):
            continue
        stance = row.get("stance")
        if stance not in {"supports", "contradicts", "neutral"}:
            stance = "supports"
        hit = hits[index - 1]
        items.append(
            EvidenceItem(
                evidence_id=f"{question_id}-E{index}-{hit.citation}",
                question_id=question_id,
                material_id=hit.material_id,
                finding=finding.strip() or hit.snippet,
                stance=stance,
                citation=hit,
            )
        )
    return tuple(items) if items else None
