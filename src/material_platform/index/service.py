from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID

from material_platform.config import Settings
from material_platform.domain.enums import MaterialType
from material_platform.domain.index_entry import IndexEntry
from material_platform.domain.research_material import ResearchMaterial
from material_platform.index.payload import (
    INDEX_VERSION,
    LEVEL_MATERIAL,
    LEVEL_UNIT,
    MATERIAL_UNIT_ID,
    make_material_point,
    make_point,
    material_text,
    unit_text,
)
from material_platform.infrastructure.embedding.factory import make_embedder
from material_platform.infrastructure.embedding.protocol import Embedder
from material_platform.infrastructure.qdrant.client import make_qdrant_client
from material_platform.infrastructure.qdrant.store import QdrantIndexStore
from material_platform.infrastructure.rerank import Reranker, make_reranker


@dataclass(frozen=True)
class ScoredEntry:
    entry: IndexEntry
    score: float


MATERIAL_HOP = 5
UNIT_HOP = 20


class IndexService:
    def __init__(
        self,
        store: QdrantIndexStore,
        embedder: Embedder,
        reranker: Reranker | None = None,
    ) -> None:
        self._store = store
        self._embedder = embedder
        self._reranker = reranker

    def replace(self, research: ResearchMaterial) -> None:
        points = []
        for unit in research.content_units:
            embedded = self._embedder.embed(unit_text(research, unit))
            points.append(make_point(research, unit, embedded))
        points.append(
            make_material_point(research, self._embedder.embed(material_text(research)))
        )
        self._store.replace(research.material_id, points)

    def search(
        self,
        query: str,
        *,
        limit: int = 5,
        material_type: str | None = None,
    ) -> tuple[ScoredEntry, ...]:
        if not query.strip():
            return ()
        kind = _normalize_type(material_type)
        embedded = self._embedder.embed(query)
        dense = list(embedded.dense)
        sparse_indices = list(embedded.sparse_indices)
        sparse_values = list(embedded.sparse_values)
        hop1 = self._store.search(
            dense=dense,
            sparse_indices=sparse_indices,
            sparse_values=sparse_values,
            limit=MATERIAL_HOP,
            level=LEVEL_MATERIAL,
            material_type=kind,
        )
        material_ids = _material_ids(hop1)
        unit_limit = max(limit, UNIT_HOP)
        if material_ids:
            hits = self._store.search(
                dense=dense,
                sparse_indices=sparse_indices,
                sparse_values=sparse_values,
                limit=unit_limit,
                level=LEVEL_UNIT,
                material_ids=material_ids,
                material_type=kind,
            )
        else:
            hits = self._store.search(
                dense=dense,
                sparse_indices=sparse_indices,
                sparse_values=sparse_values,
                limit=unit_limit,
                level=LEVEL_UNIT,
                material_type=kind,
            )
        scored: list[ScoredEntry] = []
        for hit in hits:
            entry = _from_payload(hit.id, hit.payload or {})
            if entry is None or entry.unit_id == MATERIAL_UNIT_ID:
                continue
            scored.append(ScoredEntry(entry=entry, score=float(hit.score)))
        return tuple(_rerank(self._reranker, query, scored))

    def count_for_material(self, material_id: UUID) -> int:
        return self._store.count_material(material_id)


def _rerank(
    reranker: Reranker | None, query: str, scored: list[ScoredEntry]
) -> list[ScoredEntry]:
    if reranker is None or len(scored) < 2:
        return scored
    weights = reranker.score(query, [item.entry.content for item in scored])
    if len(weights) != len(scored):
        return scored
    ranked = [
        ScoredEntry(entry=item.entry, score=weight)
        for item, weight in zip(scored, weights, strict=True)
    ]
    ranked.sort(key=lambda item: item.score, reverse=True)
    return ranked


def _normalize_type(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    kind = value.strip().lower()
    allowed = {item.value for item in MaterialType}
    if kind not in allowed:
        raise ValueError(f"unknown material_type: {value}")
    return kind


def _material_ids(hits: Sequence[object]) -> tuple[UUID, ...]:
    found: list[UUID] = []
    seen: set[UUID] = set()
    for hit in hits:
        payload = getattr(hit, "payload", None) or {}
        if not isinstance(payload, dict):
            continue
        raw = payload.get("material_id")
        if not isinstance(raw, str):
            continue
        try:
            material_id = UUID(raw)
        except ValueError:
            continue
        if material_id in seen:
            continue
        seen.add(material_id)
        found.append(material_id)
    return tuple(found)


def make_index_service(settings: Settings) -> IndexService:
    client = make_qdrant_client(settings)
    store = QdrantIndexStore(client, settings.qdrant_collection)
    return IndexService(store, make_embedder(settings), make_reranker(settings))


def _from_payload(point_id: object, payload: dict[str, object]) -> IndexEntry | None:
    material_raw = payload.get("material_id")
    unit_id = payload.get("unit_id")
    title = payload.get("title")
    content = payload.get("content")
    if not isinstance(material_raw, str) or not isinstance(unit_id, str):
        return None
    if not isinstance(title, str) or not isinstance(content, str):
        return None
    version = payload.get("index_version")
    try:
        entry_id = point_id if isinstance(point_id, UUID) else UUID(str(point_id))
        material_id = UUID(material_raw)
    except ValueError:
        return None
    return IndexEntry(
        entry_id=entry_id,
        material_id=material_id,
        unit_id=unit_id,
        index_version=version if isinstance(version, str) else INDEX_VERSION,
        title=title,
        content=content,
        path=_str(payload.get("path")),
        page=_int(payload.get("page")),
        line_start=_int(payload.get("line_start")),
        line_end=_int(payload.get("line_end")),
        section=_str(payload.get("section")),
        tokens="",
    )


def _str(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _int(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None
