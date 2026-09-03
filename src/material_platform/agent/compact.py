from __future__ import annotations

from material_platform.agent.models import ChatTurn, ConversationSummary
from material_platform.analysis.protocol import LlmClient

RECENT_TURNS = 5
_SUMMARY = 800
_TURN_ANSWER = 240
_PRIOR_RESEARCH = 400


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
    return _fallback_summary(previous, new_turns)


def clip_answer(text: str) -> str:
    lines = [line.lstrip("#").strip() for line in text.splitlines()]
    stripped = " ".join(part for part in lines if part)
    if not stripped:
        return "(no report)"
    return _clip(stripped, _TURN_ANSWER)


def clip_research(text: str) -> str:
    stripped = " ".join(text.split())
    if not stripped:
        return ""
    return _clip(stripped, _PRIOR_RESEARCH)


def standalone_question(query: str, recent: list[ChatTurn]) -> str:
    objective = query.strip()
    if not recent:
        return objective
    topic = recent[-1].query.strip()
    if topic and topic.casefold() not in objective.casefold():
        return f"{topic}: {objective}"
    return objective


def _fallback_summary(
    previous: ConversationSummary | None, new_turns: list[ChatTurn]
) -> ConversationSummary:
    decisions = [
        f"User asked {turn.query}. Assistant: {turn.answer}" for turn in new_turns
    ]
    if previous is not None:
        decisions = list(previous.important_decisions) + decisions
    goal = ""
    if previous is not None and previous.main_goal.strip():
        goal = previous.main_goal.strip()
    elif new_turns:
        goal = new_turns[0].query.strip()
    focus = new_turns[-1].query.strip() if new_turns else ""
    if previous is not None and not focus:
        focus = previous.current_focus
    scope = previous.current_scope if previous is not None else ()
    return _summary_of(
        main_goal=goal,
        current_focus=focus,
        important_decisions=tuple(decisions[-12:]),
        current_scope=scope,
    )


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
        "Update the conversation summary. Keep the current goal, focus, "
        "decisions, and scope. Do not continue the thread.\n\n"
        f"Previous summary:\n{prior}\n\nNew turns:\n"
        + "\n".join(lines)
        + '\n\nReply with one JSON object only: {"main_goal": str, '
        '"current_focus": str, "important_decisions": [str], '
        '"current_scope": [str]}'
    )
    try:
        payload = client.complete_json(prompt)
    except Exception:
        return None
    if payload.get("questions") is not None:
        return None
    goal = payload.get("main_goal")
    focus = payload.get("current_focus")
    if not isinstance(goal, str) or not goal.strip():
        return None
    if not isinstance(focus, str):
        focus = new_turns[-1].query
    return _summary_of(
        main_goal=goal,
        current_focus=focus,
        important_decisions=_string_tuple(payload.get("important_decisions")),
        current_scope=_string_tuple(payload.get("current_scope")),
    )


def _summary_of(
    *,
    main_goal: str,
    current_focus: str,
    important_decisions: tuple[str, ...],
    current_scope: tuple[str, ...],
) -> ConversationSummary:
    text = _clip(
        " ".join(
            part
            for part in (
                main_goal.strip(),
                current_focus.strip(),
                "; ".join(important_decisions),
                "; ".join(current_scope),
            )
            if part
        ),
        _SUMMARY,
    )
    return ConversationSummary(
        main_goal=_clip(main_goal.strip(), _SUMMARY),
        current_focus=_clip(current_focus.strip(), _SUMMARY),
        important_decisions=tuple(
            _clip(item, _SUMMARY) for item in important_decisions if item.strip()
        ),
        current_scope=tuple(item.strip() for item in current_scope if item.strip()),
        text=text,
    )


def _string_tuple(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(item.strip() for item in value if isinstance(item, str) and item.strip())


def _clip(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"
