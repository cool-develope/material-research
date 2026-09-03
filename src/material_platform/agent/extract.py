from __future__ import annotations

from material_platform.agent.context import for_extract, map_batches, strip_snippet
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
    question = next(
        (item.question for item in state.plan.questions if item.id == question_id),
        state.query,
    )
    with tracer.span("extract", question_id=question_id, hits=len(state.pending)):
        batches = map_batches(state.pending)
        extracted: list[EvidenceItem] = []
        offset = 1
        llm = named_llm(client, tracer, "extract")
        for batch in batches:
            items = _llm_items(question_id, question, batch, llm, offset=offset)
            if items is None:
                items = tuple(
                    _from_citation(question_id, hit, offset + index)
                    for index, hit in enumerate(batch)
                )
            extracted.extend(items)
            offset += len(batch)
        existing = [item for item in state.evidence if item.question_id == question_id]
        room = state.budgets.evidence_per_question - len(existing)
        global_room = state.budgets.evidence_total - len(state.evidence)
        take = min(room, global_room, len(extracted))
        kept = [_persist(item) for item in extracted[:take]]
        state.evidence.extend(kept)
        state.pending = []
        tracer.event(
            "extract",
            question_id=question_id,
            added=take,
            batches=len(batches),
        )
        tracer.set_output(
            {
                "question_id": question_id,
                "added": take,
                "batches": len(batches),
                "findings": [
                    {
                        "finding": clip(item.finding),
                        "stance": item.stance,
                        "citation": item.citation.citation,
                    }
                    for item in kept
                ],
            }
        )
    return state


def _persist(item: EvidenceItem) -> EvidenceItem:
    return item.model_copy(update={"citation": strip_snippet(item.citation)})


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
    question: str,
    hits: list[Citation],
    client: LlmClient | None,
    *,
    offset: int,
) -> tuple[EvidenceItem, ...] | None:
    if client is None:
        return None
    prompt = (
        "Extract grounded findings from the numbered citations. "
        "Do not invent locators. Do not continue any conversation.\n\n"
        + for_extract(question, hits)
        + '\n\nReply with one JSON object only: {"items": [{"index": 1, '
        '"finding": str, "stance": "supports"}]}'
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
                evidence_id=f"{question_id}-E{offset + index - 1}-{hit.citation}",
                question_id=question_id,
                material_id=hit.material_id,
                finding=finding.strip() or hit.snippet,
                stance=stance,
                citation=hit,
            )
        )
    return tuple(items) if items else None
