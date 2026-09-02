from material_platform.config import Settings
from material_platform.infrastructure.embedding.fake import FakeEmbedder
from material_platform.infrastructure.embedding.protocol import Embedder

_MODELS: dict[str, Embedder] = {}


def make_embedder(settings: Settings) -> Embedder:
    kind = settings.embedder.strip().lower()
    if kind in {"fake", "hash", ""}:
        return FakeEmbedder()
    if kind in {"bge-m3", "bge", "bge_m3"}:
        from material_platform.infrastructure.embedding.bge import BgeM3Embedder

        cached = _MODELS.get(settings.bge_model)
        if cached is None:
            cached = BgeM3Embedder(settings.bge_model)
            _MODELS[settings.bge_model] = cached
        return cached
    raise ValueError(f"unknown embedder: {settings.embedder}")
