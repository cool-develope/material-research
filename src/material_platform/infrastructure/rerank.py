from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from material_platform.config import Settings


class Reranker(Protocol):
    def score(self, query: str, texts: Sequence[str]) -> tuple[float, ...]: ...


class IdentityReranker:
    def score(self, query: str, texts: Sequence[str]) -> tuple[float, ...]:
        return tuple(0.0 for _ in texts)


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
        self._model = FlagReranker(model_name, use_fp16=use_cuda)

    def score(self, query: str, texts: Sequence[str]) -> tuple[float, ...]:
        if not texts:
            return ()
        pairs = [[query, text or " "] for text in texts]
        raw = self._model.compute_score(pairs, normalize=True)
        if isinstance(raw, (int, float)):
            return (float(raw),)
        return tuple(float(item) for item in raw)


def make_reranker(settings: Settings) -> Reranker | None:
    kind = settings.reranker.strip().lower()
    if kind in {"", "off", "none", "identity"}:
        return None
    if kind in {"bge-v2-m3", "bge", "bge-reranker", "bge-reranker-v2-m3"}:
        return BgeReranker(settings.bge_reranker)
    raise ValueError(f"unknown reranker: {settings.reranker}")
