from __future__ import annotations

from typing import Any

from material_platform.agent.state import AgentState

_REFERENCE = (
    "as we",
    "as you",
    "you said",
    "we said",
    "we discussed",
    "earlier",
    "previously",
    "the conclusion",
    "that finding",
    "remind",
    "as before",
)


def looks_like_reference(query: str) -> bool:
    lowered = query.lower()
    return any(token in lowered for token in _REFERENCE)


def remember(store: Any, thread_id: str, state: AgentState) -> None:
    if store is None or not thread_id:
        return
    namespace = (thread_id,)
    if state.request is not None:
        store.put(
            namespace,
            "request",
            {
                "kind": "request",
                "text": state.request.objective,
                "emphasis": state.request.emphasis,
                "constraints": list(state.request.constraints),
            },
        )
    if state.summary is not None and state.summary.text.strip():
        store.put(
            namespace,
            "summary",
            {"kind": "summary", "text": state.summary.text},
        )
    for finding in state.findings:
        store.put(
            namespace,
            f"finding-{finding.finding_id}",
            {
                "kind": "finding",
                "text": finding.claim,
                "question_id": finding.question_id,
            },
        )


def recall(store: Any, thread_id: str, query: str, *, limit: int = 5) -> str:
    if store is None or not thread_id or not looks_like_reference(query):
        return ""
    try:
        items = store.search((thread_id,), query=query, limit=limit)
    except Exception:
        return ""
    lines = ["Recalled memories:"]
    for item in items:
        value = getattr(item, "value", None)
        if not isinstance(value, dict):
            continue
        kind = value.get("kind")
        text = value.get("text")
        if not isinstance(text, str) or not text.strip():
            continue
        label = kind if isinstance(kind, str) else "memory"
        lines.append(f"- {label}: {text.strip()}")
    if len(lines) == 1:
        return ""
    return "\n".join(lines)
