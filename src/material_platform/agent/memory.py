from __future__ import annotations

import re
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
    "what else",
    "tell me more",
    "go deeper",
    "the same",
    "that paper",
    "this paper",
    "the paper",
)

_PRONOUN = re.compile(
    r"\b(it|this|that|those|them|they|its|their|same)\b", re.IGNORECASE
)


def looks_like_reference(query: str) -> bool:
    lowered = query.lower()
    if any(token in lowered for token in _REFERENCE):
        return True
    return bool(_PRONOUN.search(query))


def remember(store: Any, thread_id: str, state: AgentState) -> None:
    if store is None or not thread_id:
        return
    namespace = (thread_id,)
    objective = ""
    if state.request is not None:
        objective = state.request.objective
    elif state.plan.objective:
        objective = state.plan.objective
    if objective:
        store.put(
            namespace,
            "request",
            {
                "kind": "request",
                "text": objective,
                "emphasis": state.request.emphasis if state.request is not None else "",
                "constraints": (
                    list(state.request.constraints) if state.request is not None else []
                ),
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
