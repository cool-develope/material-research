from material_platform.config import Settings
from material_platform.infrastructure.embedding.fake import FakeEmbedder
from material_platform.infrastructure.embedding.http import HttpEmbedder
from material_platform.infrastructure.embedding.protocol import Embedder

_MODELS: dict[str, Embedder] = {}

_LOCAL = frozenset({"bge-m3", "bge", "bge_m3"})
_HTTP = frozenset({"http", "openai", "openai-compat", "remote"})


def make_embedder(settings: Settings) -> Embedder:
    kind = settings.embedder.strip().lower()
    if kind in {"fake", "hash", ""}:
        return FakeEmbedder()
    if kind in _LOCAL:
        from material_platform.infrastructure.embedding.bge import BgeM3Embedder

        cached = _MODELS.get(settings.bge_model)
        if cached is None:
            cached = BgeM3Embedder(settings.bge_model)
            _MODELS[settings.bge_model] = cached
        return cached
    if kind in _HTTP:
        if not settings.embed_base_url:
            raise ValueError("EMBEDDER=http requires EMBED_BASE_URL")
        model = settings.embed_model or settings.bge_model
        key = f"http:{settings.embed_base_url}:{model}"
        cached = _MODELS.get(key)
        if cached is None:
            cached = HttpEmbedder(
                settings.embed_base_url,
                settings.embed_api_key,
                model,
                timeout=float(settings.embed_timeout_seconds),
            )
            _MODELS[key] = cached
        return cached
    raise ValueError(f"unknown embedder: {settings.embedder}")
