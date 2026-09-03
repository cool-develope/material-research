from __future__ import annotations

import hashlib
import math

from material_platform.extraction.tokens import tokenize
from material_platform.infrastructure.embedding.protocol import (
    DENSE_SIZE,
    EmbeddedText,
)

_SPARSE_DIM = 250_002


class FakeEmbedder:
    model_name = "fake"

    def embed(self, text: str) -> EmbeddedText:
        tokens = tokenize(text)
        dense = _dense(tokens)
        counts: dict[int, float] = {}
        for token in tokens:
            index = _token_index(token)
            counts[index] = counts.get(index, 0.0) + 1.0
        if not counts:
            return EmbeddedText(dense=dense, sparse_indices=(0,), sparse_values=(1.0,))
        indices = tuple(sorted(counts))
        values = tuple(counts[index] for index in indices)
        return EmbeddedText(dense=dense, sparse_indices=indices, sparse_values=values)


def _dense(tokens: tuple[str, ...]) -> tuple[float, ...]:
    vector = [0.0] * DENSE_SIZE
    for token in tokens:
        digest = hashlib.sha256(token.encode()).hexdigest()[:8]
        vector[int(digest, 16) % DENSE_SIZE] += 1.0
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return tuple(vector)
    return tuple(value / norm for value in vector)


def _token_index(token: str) -> int:
    digest = hashlib.sha256(token.encode()).hexdigest()[:8]
    return int(digest, 16) % _SPARSE_DIM
