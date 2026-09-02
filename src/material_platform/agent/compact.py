from __future__ import annotations

from material_platform.agent.models import (
    ChatTurn,
    ConversationSummary,
    ResearchRequest,
)
from material_platform.analysis.protocol import LlmClient

RECENT_TURNS = 4
_SUMMARY = 800
_TURN_ANSWER = 240


def fold_turns(
    previous_summary: ConversationSummary | None,
    turns: list[ChatTurn],
    *,
    client: LlmClient | None = None,
) -> tuple[list[ChatTurn], ConversationSummary | None]:
    if len(turns) <= RECENT_TURNS:
        return turns, previous_summary
    overflow = turns[:-RECENT_TURNS]
    recent = turns[-RECENT_TURNS:]
    return recent, compact_summary(previous_summary, overflow, client=client)


def compact_summary(
    previous: ConversationSummary | None,
    new_turns: list[ChatTurn],
    *,
    client: LlmClient | None = None,
) -> ConversationSummary:
    drafted = _llm_summary(previous, new_turns, client)
    if drafted is not None:
        return drafted
    parts: list[str] = []
    if previous is not None and previous.text.strip():
        parts.append(previous.text.strip())
    for turn in new_turns:
        parts.append(f"User asked {turn.query}. Assistant: {turn.answer}")
    return ConversationSummary(text=_clip(" ".join(parts), _SUMMARY))


def make_request(
    query: str,
    summary: ConversationSummary | None,
    recent: list[ChatTurn],
    previous: ResearchRequest | None,
    *,
    client: LlmClient | None = None,
) -> ResearchRequest:
    drafted = _llm_request(query, summary, recent, previous, client)
    if drafted is not None:
        return drafted
    constraints = previous.constraints if previous is not None else ()
    emphasis = previous.emphasis if previous is not None else ""
    return ResearchRequest(
        objective=query.strip(),
        constraints=constraints,
        emphasis=emphasis,
    )


def clip_answer(text: str) -> str:
    stripped = " ".join(text.split())
    if not stripped:
        return "(no report)"
    return _clip(stripped, _TURN_ANSWER)


def _llm_summary(
    previous: ConversationSummary | None,
    new_turns: list[ChatTurn],
    client: LlmClient | None,
) -> ConversationSummary | None:
    if client is None or not new_turns:
        return None
    prior = previous.text if previous is not None else ""
    lines = [f"User: {turn.query}\nAssistant: {turn.answer}" for turn in new_turns]
    prompt = (
        "Update the conversation summary. Keep facts, constraints, and emphasis. "
        'JSON {"summary": str}.\n\n'
        f"Previous summary:\n{prior}\n\nNew turns:\n" + "\n".join(lines)
    )
    try:
        payload = client.complete_json(prompt)
    except Exception:
        return None
    text = payload.get("summary")
    if isinstance(text, str) and text.strip():
        if payload.get("questions") is not None:
            return None
        return ConversationSummary(text=_clip(text.strip(), _SUMMARY))
    return None


def _llm_request(
    query: str,
    summary: ConversationSummary | None,
    recent: list[ChatTurn],
    previous: ResearchRequest | None,
    client: LlmClient | None,
) -> ResearchRequest | None:
    if client is None:
        return None
    prior = ""
    if previous is not None:
        prior = (
            f"Previous request: {previous.objective}. "
            f"Emphasis: {previous.emphasis}. "
            f"Constraints: {'; '.join(previous.constraints)}"
        )
    summary_text = summary.text if summary is not None else ""
    turns = "\n".join(
        f"User: {turn.query}\nAssistant: {turn.answer}" for turn in recent
    )
    prompt = (
        "Normalize the latest user request. "
        'JSON {"objective": str, "constraints": [str], "emphasis": str}.\n\n'
        f"{prior}\nSummary:\n{summary_text}\n\nRecent:\n{turns}\n\nLatest:\n{query}"
    )
    try:
        payload = client.complete_json(prompt)
    except Exception:
        return None
    objective = payload.get("objective")
    if not isinstance(objective, str) or not objective.strip():
        return None
    if payload.get("questions") is not None:
        return None
    raw = payload.get("constraints")
    constraints: list[str] = []
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, str) and item.strip():
                constraints.append(item.strip())
    emphasis = payload.get("emphasis")
    if not isinstance(emphasis, str):
        emphasis = previous.emphasis if previous is not None else ""
    return ResearchRequest(
        objective=objective.strip(),
        constraints=tuple(constraints),
        emphasis=emphasis.strip(),
    )


def _clip(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"
