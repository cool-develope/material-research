from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

DENSE_SIZE = 1024


@dataclass(frozen=True)
class EmbeddedText:
    dense: tuple[float, ...]
    sparse_indices: tuple[int, ...]
    sparse_values: tuple[float, ...]


class Embedder(Protocol):
    def embed(self, text: str) -> EmbeddedText: ...
