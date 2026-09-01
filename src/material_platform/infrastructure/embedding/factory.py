from material_platform.config import Settings
from material_platform.infrastructure.embedding.fake import FakeEmbedder
from material_platform.infrastructure.embedding.protocol import Embedder


def make_embedder(settings: Settings) -> Embedder:
    kind = settings.embedder.strip().lower()
    if kind in {"fake", "hash", ""}:
        return FakeEmbedder()
    if kind in {"bge-m3", "bge", "bge_m3"}:
        from material_platform.infrastructure.embedding.bge import BgeM3Embedder

        return BgeM3Embedder(settings.bge_model)
    raise ValueError(f"unknown embedder: {settings.embedder}")
