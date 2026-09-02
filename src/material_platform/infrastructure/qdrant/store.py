from __future__ import annotations

from uuid import UUID

from qdrant_client import QdrantClient
from qdrant_client.http import models

from material_platform.infrastructure.embedding.protocol import DENSE_SIZE

DENSE_NAME = "dense"
SPARSE_NAME = "sparse"


class QdrantIndexStore:
    def __init__(self, client: QdrantClient, collection: str) -> None:
        self._client = client
        self._collection = collection
        _ensure_collection(client, collection)

    def replace(self, material_id: UUID, points: list[models.PointStruct]) -> None:
        self.delete_material(material_id)
        if points:
            self._client.upsert(
                collection_name=self._collection,
                points=points,
            )

    def delete_material(self, material_id: UUID) -> None:
        self._client.delete(
            collection_name=self._collection,
            points_selector=models.FilterSelector(filter=_material_filter(material_id)),
        )

    def search(
        self,
        *,
        dense: list[float],
        sparse_indices: list[int],
        sparse_values: list[float],
        limit: int,
        level: str | None = None,
        material_ids: tuple[UUID, ...] | None = None,
        material_type: str | None = None,
    ) -> list[models.ScoredPoint]:
        prefetch = max(limit * 4, 20)
        query_filter = _payload_filter(level, material_ids, material_type)
        sparse = models.SparseVector(
            indices=sparse_indices,
            values=sparse_values,
        )
        result = self._client.query_points(
            collection_name=self._collection,
            prefetch=[
                models.Prefetch(
                    query=dense,
                    using=DENSE_NAME,
                    limit=prefetch,
                    filter=query_filter,
                ),
                models.Prefetch(
                    query=sparse,
                    using=SPARSE_NAME,
                    limit=prefetch,
                    filter=query_filter,
                ),
            ],
            query=models.FusionQuery(fusion=models.Fusion.RRF),
            query_filter=query_filter,
            limit=limit,
            with_payload=True,
        )
        return list(result.points)

    def count_material(self, material_id: UUID) -> int:
        result = self._client.count(
            collection_name=self._collection,
            count_filter=_material_filter(material_id),
            exact=True,
        )
        return int(result.count)

    def recreate(self) -> None:
        if self._client.collection_exists(self._collection):
            self._client.delete_collection(self._collection)
        _ensure_collection(self._client, self._collection)


def _payload_filter(
    level: str | None,
    material_ids: tuple[UUID, ...] | None,
    material_type: str | None = None,
) -> models.Filter | None:
    must: list[models.Condition] = []
    if level:
        must.append(
            models.FieldCondition(
                key="level",
                match=models.MatchValue(value=level),
            )
        )
    if material_ids:
        must.append(
            models.FieldCondition(
                key="material_id",
                match=models.MatchAny(any=[str(item) for item in material_ids]),
            )
        )
    if material_type:
        must.append(
            models.FieldCondition(
                key="material_type",
                match=models.MatchValue(value=material_type),
            )
        )
    if not must:
        return None
    return models.Filter(must=must)


def _material_filter(material_id: UUID) -> models.Filter:
    return models.Filter(
        must=[
            models.FieldCondition(
                key="material_id",
                match=models.MatchValue(value=str(material_id)),
            )
        ]
    )


def _ensure_collection(client: QdrantClient, collection: str) -> None:
    if client.collection_exists(collection):
        _assert_hybrid_collection(client, collection)
        return
    client.create_collection(
        collection_name=collection,
        vectors_config={
            DENSE_NAME: models.VectorParams(
                size=DENSE_SIZE,
                distance=models.Distance.COSINE,
            )
        },
        sparse_vectors_config={
            SPARSE_NAME: models.SparseVectorParams(),
        },
    )
    if _is_local(client):
        return
    client.create_payload_index(
        collection_name=collection,
        field_name="material_id",
        field_schema=models.PayloadSchemaType.KEYWORD,
    )
    client.create_payload_index(
        collection_name=collection,
        field_name="level",
        field_schema=models.PayloadSchemaType.KEYWORD,
    )
    client.create_payload_index(
        collection_name=collection,
        field_name="material_type",
        field_schema=models.PayloadSchemaType.KEYWORD,
    )


def _assert_hybrid_collection(client: QdrantClient, collection: str) -> None:
    info = client.get_collection(collection)
    vectors = info.config.params.vectors
    dense = vectors.get(DENSE_NAME) if isinstance(vectors, dict) else None
    size = getattr(dense, "size", None)
    if size != DENSE_SIZE:
        raise RuntimeError(
            f"Qdrant collection {collection!r} dense size {size} != {DENSE_SIZE}"
        )
    sparse = info.config.params.sparse_vectors or {}
    if SPARSE_NAME not in sparse:
        raise RuntimeError(
            f"Qdrant collection {collection!r} is missing sparse vector {SPARSE_NAME!r}"
        )


def _is_local(client: QdrantClient) -> bool:
    inner = getattr(client, "_client", None)
    return type(inner).__name__ == "QdrantLocal"
