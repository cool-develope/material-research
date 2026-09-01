from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from material_platform.config import Settings
from material_platform.domain.index_entry import IndexEntry
from material_platform.domain.research_material import ResearchMaterial
from material_platform.index.payload import (
    INDEX_VERSION,
    make_point,
    unit_text,
)
from material_platform.infrastructure.embedding.factory import make_embedder
from material_platform.infrastructure.embedding.protocol import Embedder
from material_platform.infrastructure.qdrant.client import make_qdrant_client
from material_platform.infrastructure.qdrant.store import QdrantIndexStore


@dataclass(frozen=True)
class ScoredEntry:
    entry: IndexEntry
    score: float


class IndexService:
    def __init__(self, store: QdrantIndexStore, embedder: Embedder) -> None:
        self._store = store
        self._embedder = embedder

    def replace(self, research: ResearchMaterial) -> None:
        points = []
        for unit in research.content_units:
            embedded = self._embedder.embed(unit_text(research, unit))
            points.append(make_point(research, unit, embedded))
        self._store.replace(research.material_id, points)

    def search(self, query: str, *, limit: int = 5) -> tuple[ScoredEntry, ...]:
        if not query.strip():
            return ()
        embedded = self._embedder.embed(query)
        hits = self._store.search(
            dense=list(embedded.dense),
            sparse_indices=list(embedded.sparse_indices),
            sparse_values=list(embedded.sparse_values),
            limit=limit,
        )
        scored: list[ScoredEntry] = []
        for hit in hits:
            entry = _from_payload(hit.id, hit.payload or {})
            if entry is not None:
                scored.append(ScoredEntry(entry=entry, score=float(hit.score)))
        return tuple(scored)

    def count_for_material(self, material_id: UUID) -> int:
        return self._store.count_material(material_id)


def make_index_service(settings: Settings) -> IndexService:
    client = make_qdrant_client(settings)
    store = QdrantIndexStore(client, settings.qdrant_collection)
    return IndexService(store, make_embedder(settings))


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
