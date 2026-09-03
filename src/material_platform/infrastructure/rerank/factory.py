from __future__ import annotations

from material_platform.config import Settings
from material_platform.infrastructure.rerank.bge import BgeReranker
from material_platform.infrastructure.rerank.http import HttpReranker
from material_platform.infrastructure.rerank.protocol import Reranker

_MODELS: dict[str, Reranker] = {}

_LOCAL = frozenset(
    {
        "on",
        "true",
        "bge-v2-m3",
        "bge",
        "bge-reranker",
        "bge-reranker-v2-m3",
    }
)
_HTTP = frozenset({"http", "openai", "openai-compat", "remote", "tei"})


def make_reranker(settings: Settings) -> Reranker | None:
    kind = settings.reranker.strip().lower()
    if kind in {"", "off", "none", "identity"}:
        return None
    if kind in _LOCAL:
        cached = _MODELS.get(settings.bge_reranker)
        if cached is None:
            cached = BgeReranker(settings.bge_reranker)
            _MODELS[settings.bge_reranker] = cached
        return cached
    if kind in _HTTP:
        if not settings.rerank_base_url:
            raise ValueError("RERANKER=http requires RERANK_BASE_URL")
        model = settings.rerank_model or settings.bge_reranker
        key = f"http:{settings.rerank_base_url}:{model}"
        cached = _MODELS.get(key)
        if cached is None:
            cached = HttpReranker(
                settings.rerank_base_url,
                settings.rerank_api_key,
                model,
                timeout=float(settings.rerank_timeout_seconds),
            )
            _MODELS[key] = cached
        return cached
    raise ValueError(f"unknown reranker: {settings.reranker}")
