from __future__ import annotations

from collections.abc import Sequence

from material_platform.infrastructure.http import post_json
from material_platform.infrastructure.rerank.protocol import clip_rerank_text


class HttpReranker:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        *,
        timeout: float = 120,
    ) -> None:
        self.model_name = model
        self._url = base_url.rstrip("/") + "/rerank"
        self._api_key = api_key
        self._timeout = timeout

    def score(self, query: str, texts: Sequence[str]) -> tuple[float, ...]:
        if not texts:
            return ()
        clipped = [clip_rerank_text(text) for text in texts]
        payload = post_json(
            self._url,
            {"model": self.model_name, "query": query, "texts": clipped},
            api_key=self._api_key,
            timeout=self._timeout,
        )
        scores = _scores(payload, expected=len(clipped))
        return scores


def _scores(payload: object, *, expected: int) -> tuple[float, ...]:
    values = _score_list(payload)
    if values is None:
        values = _score_results(payload)
    if values is None:
        raise RuntimeError("rerank response has no scores")
    if len(values) != expected:
        raise RuntimeError(
            f"rerank score count {len(values)} != {expected}"
        )
    return values


def _score_list(payload: object) -> tuple[float, ...] | None:
    if isinstance(payload, dict):
        raw = payload.get("scores")
        if isinstance(raw, list) and raw:
            return tuple(float(item) for item in raw)
    return None


def _score_results(payload: object) -> tuple[float, ...] | None:
    rows: object
    if isinstance(payload, list):
        rows = payload
    elif isinstance(payload, dict):
        rows = payload.get("results")
    else:
        return None
    if not isinstance(rows, list) or not rows:
        return None
    ranked: dict[int, float] = {}
    for offset, item in enumerate(rows):
        if not isinstance(item, dict):
            return None
        index = item.get("index", offset)
        if not isinstance(index, int):
            return None
        score = item.get("score", item.get("relevance_score"))
        if not isinstance(score, (int, float)):
            return None
        ranked[index] = float(score)
    return tuple(ranked[index] for index in sorted(ranked))
