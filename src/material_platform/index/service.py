from __future__ import annotations

from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from uuid import UUID

from material_platform.config import Settings
from material_platform.domain.enums import MaterialType
from material_platform.domain.index_entry import IndexEntry
from material_platform.domain.research_material import (
    ContentLocation,
    ResearchMaterial,
    format_location,
)
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
from material_platform.infrastructure.rerank import (
    RERANK_CHARS,
    Reranker,
    clip_rerank_text,
    make_reranker,
)

_TITLE = 80


@dataclass(frozen=True)
class ScoredEntry:
    entry: IndexEntry
    score: float


@dataclass(frozen=True)
class SearchDetail:
    hop1: tuple[ScoredEntry, ...]
    hop2: tuple[ScoredEntry, ...]
    ranked: tuple[ScoredEntry, ...]
    reranked: bool


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
        return self.search_detail(
            query, limit=limit, material_type=material_type
        ).ranked

    def search_detail(
        self,
        query: str,
        *,
        limit: int = 5,
        material_type: str | None = None,
        tracer: object | None = None,
    ) -> SearchDetail:
        log = tracer if tracer is not None else _NoopLog()
        if not query.strip():
            return SearchDetail(hop1=(), hop2=(), ranked=(), reranked=False)
        kind = _normalize_type(material_type)
        model = _model_name(self._embedder)
        with log.span("embed", model=model, chars=len(query)):
            embedded = self._embedder.embed(query)
            log.set_output(
                {
                    "model": model,
                    "chars": len(query),
                    "dense": len(embedded.dense),
                    "sparse": len(embedded.sparse_indices),
                }
            )
        dense = list(embedded.dense)
        sparse_indices = list(embedded.sparse_indices)
        sparse_values = list(embedded.sparse_values)
        with log.span("hop1", k=MATERIAL_HOP, level="material"):
            hop1_points = self._store.search(
                dense=dense,
                sparse_indices=sparse_indices,
                sparse_values=sparse_values,
                limit=MATERIAL_HOP,
                level=LEVEL_MATERIAL,
                material_type=kind,
            )
            hop1 = _scored_points(hop1_points)
            log.set_output(_brief_materials(hop1))
        material_ids = tuple(item.entry.material_id for item in hop1)
        unit_limit = min(max(limit, 1), UNIT_HOP)
        with log.span("hop2", k=unit_limit, materials=len(hop1), level="unit"):
            if material_ids:
                unit_points = self._store.search(
                    dense=dense,
                    sparse_indices=sparse_indices,
                    sparse_values=sparse_values,
                    limit=unit_limit,
                    level=LEVEL_UNIT,
                    material_ids=material_ids,
                    material_type=kind,
                )
            else:
                unit_points = self._store.search(
                    dense=dense,
                    sparse_indices=sparse_indices,
                    sparse_values=sparse_values,
                    limit=unit_limit,
                    level=LEVEL_UNIT,
                    material_type=kind,
                )
            hop2 = tuple(
                item
                for item in _scored_points(unit_points)
                if item.entry.unit_id != MATERIAL_UNIT_ID
            )
            log.set_output(_brief_units(hop2))
        reranked = self._reranker is not None and len(hop2) >= 2
        with log.span(
            "rerank",
            enabled=reranked,
            model=_model_name(self._reranker) if reranked else None,
            docs=len(hop2),
        ):
            ranked = tuple(_rerank(self._reranker, query, list(hop2)))
            chars = (
                sum(len(clip_rerank_text(item.entry.content)) for item in hop2)
                if reranked
                else 0
            )
            log.set_output(
                {
                    "enabled": reranked,
                    "docs": len(hop2),
                    "chars": chars,
                    "cap": RERANK_CHARS if reranked else 0,
                    "top": _location_label(ranked[0].entry) if ranked else None,
                }
            )
        return SearchDetail(hop1=hop1, hop2=hop2, ranked=ranked, reranked=reranked)

    def count_for_material(self, material_id: UUID) -> int:
        return self._store.count_material(material_id)

    def wipe(self) -> None:
        self._store.recreate()


def _scored_points(hits: Sequence[object]) -> tuple[ScoredEntry, ...]:
    scored: list[ScoredEntry] = []
    for hit in hits:
        payload = getattr(hit, "payload", None) or {}
        if not isinstance(payload, dict):
            continue
        entry = _from_payload(getattr(hit, "id", None), payload)
        if entry is None:
            continue
        scored.append(ScoredEntry(entry=entry, score=float(getattr(hit, "score", 0.0))))
    return tuple(scored)


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


class _NoopLog:
    @contextmanager
    def span(self, name: str, **attrs: object) -> Iterator[None]:
        yield

    def set_output(self, value: object) -> None:
        return None


def _model_name(obj: object | None) -> str:
    if obj is None:
        return ""
    name = getattr(obj, "model_name", None)
    if isinstance(name, str) and name:
        return name
    return type(obj).__name__


def _brief_materials(hits: tuple[ScoredEntry, ...]) -> dict[str, object]:
    top = _clip(hits[0].entry.title) if hits else None
    return {"hits": len(hits), "top": top}


def _brief_units(hits: tuple[ScoredEntry, ...]) -> dict[str, object]:
    top = _location_label(hits[0].entry) if hits else None
    return {"hits": len(hits), "top": top}


def _location_label(entry: IndexEntry) -> str:
    return (
        format_location(
            ContentLocation(
                path=entry.path,
                page=entry.page,
                line_start=entry.line_start,
                line_end=entry.line_end,
                section=entry.section,
            )
        )
        or entry.title
    )


def _clip(text: str) -> str:
    stripped = " ".join(text.split())
    if len(stripped) <= _TITLE:
        return stripped
    return stripped[: _TITLE - 1] + "…"


def _normalize_type(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    kind = value.strip().lower()
    allowed = {item.value for item in MaterialType}
    if kind not in allowed:
        raise ValueError(f"unknown material_type: {value}")
    return kind


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
