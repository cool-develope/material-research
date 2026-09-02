from __future__ import annotations

from material_platform.agent.models import Finding, ReportSection
from material_platform.agent.state import AgentState
from material_platform.domain.citation import Citation

MAP_CHARS = 8000


def for_plan(state: AgentState) -> str:
    parts: list[str] = []
    if state.summary is not None and state.summary.text.strip():
        parts.append(f"Conversation summary: {state.summary.text.strip()}")
    if state.conversation:
        parts.append("Recent turns:")
        for turn in state.conversation:
            parts.append(f"User: {turn.query}")
            parts.append(f"Assistant: {turn.answer}")
    if state.request is not None:
        parts.append(f"Research request: {state.request.objective}")
        if state.request.emphasis:
            parts.append(f"Emphasis: {state.request.emphasis}")
        if state.request.constraints:
            parts.append("Constraints: " + "; ".join(state.request.constraints))
    if state.recalled.strip():
        parts.append(state.recalled.strip())
    return "\n".join(parts)


def for_extract(question: str, hits: list[Citation]) -> str:
    lines = [f"Question: {question}"]
    for index, hit in enumerate(hits, start=1):
        lines.append(f"{index}. {hit.citation} :: {hit.snippet}")
    return "\n".join(lines)


def for_write_section(objective: str, heading: str, body: str) -> str:
    return (
        "Rewrite this section in 1-3 sentences. Keep every citation string "
        'unchanged. JSON {"body": str}.\n\n'
        f"Objective: {objective}\nHeading: {heading}\n{body}"
    )


def for_summary(objective: str, sections: list[ReportSection]) -> str:
    return (
        "Write a 2-sentence executive summary last, after these sections. "
        'JSON {"summary": str}. Do not add citations that are not listed.\n\n'
        f"Objective: {objective}\n\n"
        + "\n\n".join(f"## {item.heading}\n{item.body}" for item in sections)
    )


def for_follow_up(question: str, draft: str, state: AgentState) -> str:
    searches = [item.query for item in state.history][-6:]
    prior = f"\nPrior searches: {'; '.join(searches)}" if searches else ""
    return f"Question: {question}\nDraft: {draft}{prior}"


def map_batches(
    hits: list[Citation], *, budget: int = MAP_CHARS
) -> list[list[Citation]]:
    batches: list[list[Citation]] = []
    current: list[Citation] = []
    size = 0
    for hit in hits:
        piece = max(1, len(hit.citation) + len(hit.snippet or ""))
        if current and size + piece > budget:
            batches.append(current)
            current = []
            size = 0
        current.append(hit)
        size += piece
    if current:
        batches.append(current)
    return batches


def strip_snippet(hit: Citation) -> Citation:
    if not hit.snippet:
        return hit
    return hit.model_copy(update={"snippet": ""})


def finding_for(state: AgentState, question_id: str) -> Finding | None:
    return next(
        (item for item in state.findings if item.question_id == question_id),
        None,
    )
