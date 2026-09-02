from __future__ import annotations

import hashlib

from material_platform.infrastructure.embedding.protocol import (
    DENSE_SIZE,
    EmbeddedText,
)

_SPARSE_DIM = 250_002


class BgeM3Embedder:
    def __init__(self, model_name: str = "BAAI/bge-m3") -> None:
        try:
            import torch
            from FlagEmbedding import BGEM3FlagModel
        except ImportError as exc:
            raise RuntimeError(
                "BGE-M3 needs FlagEmbedding. Install CPU torch, then "
                "FlagEmbedding: uv pip install torch --index-url "
                "https://download.pytorch.org/whl/cpu && "
                "uv pip install FlagEmbedding"
            ) from exc
        use_cuda = torch.cuda.is_available()
        self.model_name = model_name
        self._model = BGEM3FlagModel(
            model_name,
            use_fp16=use_cuda,
            devices="cuda:0" if use_cuda else "cpu",
            batch_size=1,
            query_max_length=512,
            passage_max_length=512,
            return_dense=True,
            return_sparse=True,
            return_colbert_vecs=False,
        )

    def embed(self, text: str) -> EmbeddedText:
        output = self._model.encode(
            [text or " "],
            return_dense=True,
            return_sparse=True,
            return_colbert_vecs=False,
            batch_size=1,
        )
        dense = _as_floats(output["dense_vecs"][0])
        if len(dense) != DENSE_SIZE:
            raise RuntimeError(f"BGE-M3 dense size {len(dense)} != {DENSE_SIZE}")
        indices, values = _sparse(output["lexical_weights"][0])
        return EmbeddedText(
            dense=dense,
            sparse_indices=indices,
            sparse_values=values,
        )


def _as_floats(values: object) -> tuple[float, ...]:
    raw: object = values
    to_list = getattr(raw, "tolist", None)
    if callable(to_list):
        raw = to_list()
    if isinstance(raw, list):
        return tuple(float(item) for item in raw)
    if isinstance(raw, tuple):
        return tuple(float(item) for item in raw)
    raise TypeError(f"cannot convert {type(values).__name__} to floats")


def _sparse(weights: object) -> tuple[tuple[int, ...], tuple[float, ...]]:
    if not isinstance(weights, dict) or not weights:
        return (0,), (1.0,)
    combined: dict[int, float] = {}
    for key, weight in weights.items():
        index = _sparse_index(key)
        combined[index] = combined.get(index, 0.0) + float(weight)
    indices = tuple(sorted(combined))
    return indices, tuple(combined[index] for index in indices)


def _sparse_index(key: object) -> int:
    if isinstance(key, int):
        return key % _SPARSE_DIM
    if isinstance(key, str) and key.isdigit():
        return int(key) % _SPARSE_DIM
    digest = hashlib.sha256(str(key).encode()).hexdigest()[:8]
    return int(digest, 16) % _SPARSE_DIM
