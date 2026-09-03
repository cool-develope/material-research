from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

RERANK_CHARS = 2048


class Reranker(Protocol):
    def score(self, query: str, texts: Sequence[str]) -> tuple[float, ...]: ...


def clip_rerank_text(text: str) -> str:
    stripped = text or " "
    if len(stripped) <= RERANK_CHARS:
        return stripped
    return stripped[:RERANK_CHARS]
