import pytest

from material_platform.config import Settings
from material_platform.infrastructure.rerank import IdentityReranker, make_reranker


def test_make_reranker_defaults_off() -> None:
    assert make_reranker(Settings(_env_file=None)) is None


def test_make_reranker_rejects_unknown() -> None:
    with pytest.raises(ValueError, match="unknown reranker"):
        make_reranker(Settings(_env_file=None, reranker="nope"))


def test_identity_reranker_keeps_length() -> None:
    scores = IdentityReranker().score("q", ("a", "b"))
    assert scores == (0.0, 0.0)
