import json
from io import BytesIO
from urllib.error import HTTPError

import pytest

from material_platform.config import Settings
from material_platform.infrastructure.embedding.factory import make_embedder
from material_platform.infrastructure.embedding.http import HttpEmbedder
from material_platform.infrastructure.embedding.protocol import DENSE_SIZE
from material_platform.infrastructure.rerank.factory import make_reranker
from material_platform.infrastructure.rerank.http import HttpReranker


class _Response:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def read(self) -> bytes:
        return self._payload

    def __enter__(self) -> "_Response":
        return self

    def __exit__(self, *_args: object) -> None:
        return None


def test_make_embedder_http_requires_url() -> None:
    with pytest.raises(ValueError, match="EMBED_BASE_URL"):
        make_embedder(Settings(_env_file=None, embedder="http"))


def test_http_embedder_reads_openai_embeddings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dense = [0.0] * DENSE_SIZE
    dense[0] = 1.0

    def fake_urlopen(request: object, timeout: float = 0) -> _Response:
        assert timeout == 5
        return _Response(
            json.dumps({"data": [{"embedding": dense, "index": 0}]}).encode()
        )

    monkeypatch.setattr(
        "material_platform.infrastructure.http.urlopen", fake_urlopen
    )
    embedder = HttpEmbedder(
        "http://embed.example/v1", "key", "bge-m3", timeout=5
    )
    embedded = embedder.embed("hello")
    assert embedded.dense[0] == 1.0
    assert len(embedded.dense) == DENSE_SIZE
    assert embedded.sparse_indices == (0,)


def test_http_embedder_rejects_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(request: object, timeout: float = 0) -> _Response:
        raise HTTPError(
            "http://embed.example/v1/embeddings",
            503,
            "busy",
            hdrs={},
            fp=BytesIO(),
        )

    monkeypatch.setattr("material_platform.infrastructure.http.urlopen", boom)
    embedder = HttpEmbedder("http://embed.example/v1", "key", "bge-m3")
    with pytest.raises(RuntimeError, match="HTTP 503"):
        embedder.embed("hello")


def test_make_reranker_http_requires_url() -> None:
    with pytest.raises(ValueError, match="RERANK_BASE_URL"):
        make_reranker(Settings(_env_file=None, reranker="http"))


def test_http_reranker_reads_scores(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(request: object, timeout: float = 0) -> _Response:
        return _Response(b'{"scores": [0.2, 0.9]}')

    monkeypatch.setattr(
        "material_platform.infrastructure.http.urlopen", fake_urlopen
    )
    reranker = HttpReranker("http://rerank.example", "key", "bge-reranker")
    assert reranker.score("q", ["a", "b"]) == (0.2, 0.9)


def test_http_reranker_reads_tei_results(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(request: object, timeout: float = 0) -> _Response:
        return _Response(
            b'{"results": [{"index": 1, "relevance_score": 0.1},'
            b' {"index": 0, "relevance_score": 0.8}]}'
        )

    monkeypatch.setattr(
        "material_platform.infrastructure.http.urlopen", fake_urlopen
    )
    reranker = HttpReranker("http://rerank.example", "key", "tei")
    assert reranker.score("q", ["a", "b"]) == (0.8, 0.1)


def test_make_embedder_http_reuses_client() -> None:
    from material_platform.infrastructure.embedding import factory as embed_factory

    embed_factory._MODELS.clear()
    settings = Settings(
        _env_file=None,
        embedder="http",
        embed_base_url="http://embed.example/v1",
    )
    first = make_embedder(settings)
    second = make_embedder(settings)
    assert first is second
    embed_factory._MODELS.clear()
