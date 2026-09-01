from qdrant_client import QdrantClient

from material_platform.index.service import IndexService
from material_platform.infrastructure.embedding.fake import FakeEmbedder
from material_platform.infrastructure.qdrant.store import QdrantIndexStore


def make_test_index() -> IndexService:
    return IndexService(
        QdrantIndexStore(QdrantClient(":memory:"), "research"),
        FakeEmbedder(),
    )
