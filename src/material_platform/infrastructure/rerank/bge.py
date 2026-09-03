from __future__ import annotations

from collections.abc import Sequence

from material_platform.infrastructure.rerank.protocol import clip_rerank_text


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
