from __future__ import annotations

from material_platform.infrastructure.embedding.protocol import (
    DENSE_SIZE,
    EmbeddedText,
)
from material_platform.infrastructure.http import post_json


class HttpEmbedder:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        *,
        timeout: float = 120,
    ) -> None:
        self.model_name = model
        self._url = base_url.rstrip("/") + "/embeddings"
        self._api_key = api_key
        self._timeout = timeout

    def embed(self, text: str) -> EmbeddedText:
        payload = post_json(
            self._url,
            {"model": self.model_name, "input": text or " "},
            api_key=self._api_key,
            timeout=self._timeout,
        )
        dense = _embedding(payload)
        if len(dense) != DENSE_SIZE:
            raise RuntimeError(f"embed dense size {len(dense)} != {DENSE_SIZE}")
        return EmbeddedText(
            dense=dense,
            sparse_indices=(0,),
            sparse_values=(1.0,),
        )


def _embedding(payload: object) -> tuple[float, ...]:
    if not isinstance(payload, dict):
        raise RuntimeError("embed response is not an object")
    data = payload.get("data")
    if not isinstance(data, list) or not data:
        raise RuntimeError("embed response has no data")
    first = data[0]
    if not isinstance(first, dict):
        raise RuntimeError("embed item is not an object")
    raw = first.get("embedding")
    if not isinstance(raw, list) or not raw:
        raise RuntimeError("embed item has no embedding")
    return tuple(float(item) for item in raw)
