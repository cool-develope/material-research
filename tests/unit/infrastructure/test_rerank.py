import pytest

from material_platform.config import Settings
from material_platform.infrastructure import rerank as rerank_mod
from material_platform.infrastructure.rerank import (
    RERANK_CHARS,
    clip_rerank_text,
    make_reranker,
)


def test_make_reranker_defaults_off() -> None:
    assert make_reranker(Settings(_env_file=None)) is None


def test_make_reranker_on_is_bge_alias(monkeypatch: pytest.MonkeyPatch) -> None:
    class Fake:
        def __init__(self, name: str) -> None:
            self.name = name

    rerank_mod._MODELS.clear()
    monkeypatch.setattr("material_platform.infrastructure.rerank.BgeReranker", Fake)
    reranker = make_reranker(Settings(_env_file=None, reranker="on"))
    assert isinstance(reranker, Fake)
    assert reranker.name == "BAAI/bge-reranker-v2-m3"
    again = make_reranker(Settings(_env_file=None, reranker="on"))
    assert again is reranker
    rerank_mod._MODELS.clear()


def test_clip_rerank_text_caps_long_passages() -> None:
    assert clip_rerank_text("short") == "short"
    assert len(clip_rerank_text("x" * (RERANK_CHARS + 50))) == RERANK_CHARS


def test_make_reranker_rejects_unknown() -> None:
    with pytest.raises(ValueError, match="unknown reranker"):
        make_reranker(Settings(_env_file=None, reranker="nope"))
