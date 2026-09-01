from qdrant_client import QdrantClient

from material_platform.index.service import IndexService
from material_platform.infrastructure.embedding.fake import FakeEmbedder
from material_platform.infrastructure.qdrant.store import QdrantIndexStore
from material_platform.infrastructure.rerank import Reranker


def make_test_index(reranker: Reranker | None = None) -> IndexService:
    return IndexService(
        QdrantIndexStore(QdrantClient(":memory:"), "research"),
        FakeEmbedder(),
        reranker,
    )
