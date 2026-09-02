from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from material_platform.config import Settings

RERANK_CHARS = 2048


class Reranker(Protocol):
    def score(self, query: str, texts: Sequence[str]) -> tuple[float, ...]: ...


class BgeReranker:
    def __init__(self, model_name: str = "BAAI/bge-reranker-v2-m3") -> None:
        try:
            import torch
            from FlagEmbedding import FlagReranker
        except ImportError as exc:
            raise RuntimeError(
                "bge-reranker-v2-m3 needs FlagEmbedding. Install CPU torch, then "
                "FlagEmbedding."
            ) from exc
        use_cuda = torch.cuda.is_available()
        self.model_name = model_name
        self._model = FlagReranker(model_name, use_fp16=use_cuda, max_length=512)

    def score(self, query: str, texts: Sequence[str]) -> tuple[float, ...]:
        if not texts:
            return ()
        pairs = [[query, clip_rerank_text(text)] for text in texts]
        raw = self._model.compute_score(pairs, normalize=True)
        if isinstance(raw, (int, float)):
            return (float(raw),)
        return tuple(float(item) for item in raw)


_MODELS: dict[str, BgeReranker] = {}


def clip_rerank_text(text: str) -> str:
    stripped = text or " "
    if len(stripped) <= RERANK_CHARS:
        return stripped
    return stripped[:RERANK_CHARS]


def make_reranker(settings: Settings) -> Reranker | None:
    kind = settings.reranker.strip().lower()
    if kind in {"", "off", "none", "identity"}:
        return None
    if kind in {
        "on",
        "true",
        "bge-v2-m3",
        "bge",
        "bge-reranker",
        "bge-reranker-v2-m3",
    }:
        cached = _MODELS.get(settings.bge_reranker)
        if cached is None:
            cached = BgeReranker(settings.bge_reranker)
            _MODELS[settings.bge_reranker] = cached
        return cached
    raise ValueError(f"unknown reranker: {settings.reranker}")
