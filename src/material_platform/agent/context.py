from __future__ import annotations

from material_platform.agent.state import AgentState
from material_platform.domain.citation import Citation
from material_platform.domain.research import Finding, ReportSection

MAP_CHARS = 8000


def chat_context(state: AgentState) -> str:
    parts: list[str] = ["<thread>"]
    if state.summary is not None:
        summary = state.summary
        if summary.main_goal.strip():
            parts.append(f"Main goal: {summary.main_goal.strip()}")
        if summary.current_focus.strip():
            parts.append(f"Current focus: {summary.current_focus.strip()}")
        if summary.important_decisions:
            parts.append(
                "Important decisions: " + "; ".join(summary.important_decisions)
            )
        if summary.current_scope:
            parts.append("Current scope: " + "; ".join(summary.current_scope))
        if (
            not summary.main_goal.strip()
            and not summary.current_focus.strip()
            and summary.text.strip()
        ):
            parts.append(f"Conversation summary: {summary.text.strip()}")
    if state.conversation:
        parts.append("Recent turns:")
        for turn in state.conversation:
            parts.append(f"Past user: {turn.query}")
            parts.append(f"Past assistant: {turn.answer}")
    if state.prior_research.strip():
        parts.append(f"Previous research: {state.prior_research.strip()}")
    parts.append(f"Latest user message: {state.query}")
    parts.append("</thread>")
    return "\n".join(parts)


def for_plan(state: AgentState) -> str:
    return chat_context(state)


def for_extract(question: str, hits: list[Citation]) -> str:
    lines = [f"Question: {question}"]
    for index, hit in enumerate(hits, start=1):
        lines.append(f"{index}. {hit.citation} :: {hit.snippet}")
    return "\n".join(lines)


def for_write_section(
    objective: str, heading: str, body: str, *, context: str = ""
) -> str:
    prior = f"{context}\n\n" if context.strip() else ""
    return (
        "Rewrite this section in 1-3 sentences. Keep every citation string "
        "unchanged. Use the thread only as context; do not continue it.\n\n"
        f"{prior}"
        f"Objective: {objective}\nHeading: {heading}\n{body}\n\n"
        'Reply with one JSON object only: {"body": str}'
    )


def for_summary(
    objective: str, sections: list[ReportSection], *, context: str = ""
) -> str:
    prior = f"{context}\n\n" if context.strip() else ""
    return (
        "Write a 2-sentence executive summary last, after these sections. "
        "Use the thread only as context. Do not add citations that are not listed.\n\n"
        f"{prior}"
        f"Objective: {objective}\n\n"
        + "\n\n".join(f"## {item.heading}\n{item.body}" for item in sections)
        + '\n\nReply with one JSON object only: {"summary": str}'
    )


def for_gap(state: AgentState) -> str:
    lines = [chat_context(state), "Questions:"]
    for question in state.plan.questions:
        row = state.questions.get(question.id)
        status = row.status if row is not None else "pending"
        last = row.last_query if row is not None else ""
        lines.append(f"- {question.id} [{status}] {question.question} last={last}")
    return "\n".join(lines)


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
