import os

import pytest

from material_platform.config import Settings
from material_platform.infrastructure.embedding.factory import make_embedder
from material_platform.infrastructure.embedding.fake import FakeEmbedder
from material_platform.infrastructure.embedding.protocol import DENSE_SIZE


def test_make_embedder_defaults_to_fake() -> None:
    embedder = make_embedder(Settings(_env_file=None))
    assert isinstance(embedder, FakeEmbedder)
    embedded = embedder.embed("handle_request")
    assert len(embedded.dense) == DENSE_SIZE
    assert embedded.sparse_indices
    assert embedded.sparse_values


def test_make_embedder_rejects_unknown() -> None:
    with pytest.raises(ValueError, match="unknown embedder"):
        make_embedder(Settings(_env_file=None, embedder="nope"))


@pytest.mark.skipif(
    os.environ.get("RUN_BGE") != "1", reason="set RUN_BGE=1 to load BGE-M3"
)
def test_bge_m3_embed_dense_and_sparse() -> None:
    embedder = make_embedder(Settings(_env_file=None, embedder="bge-m3"))
    embedded = embedder.embed("handle_request")
    assert len(embedded.dense) == DENSE_SIZE
    assert abs(sum(value * value for value in embedded.dense) - 1.0) < 0.05
    assert len(embedded.sparse_indices) > 1
    assert len(embedded.sparse_indices) == len(embedded.sparse_values)
