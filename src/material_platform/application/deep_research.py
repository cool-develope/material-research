from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from material_platform.application.index import IndexService, ScoredEntry
from material_platform.domain.analysis import MaterialAnalysis
from material_platform.domain.citation import Citation
from material_platform.domain.enums import MaterialStatus
from material_platform.domain.index_entry import IndexEntry
from material_platform.domain.material import Material
from material_platform.domain.research_material import ContentLocation, format_location
from material_platform.infrastructure.database.repositories import (
    ArtifactRepository,
    MaterialRepository,
)
from material_platform.infrastructure.object_store.protocol import ObjectStore
from material_platform.infrastructure.qdrant.payload import MATERIAL_UNIT_ID

_SNIPPET = 180
_SOURCE_BOOST = 0.05
_MAX_SIBLINGS = 4
_MAX_KEYWORDS = 8
_TYPE_ORDER = {
    "document": 0,
    "project": 1,
    "dataset": 2,
    "code": 3,
}


@dataclass(frozen=True)
class MaterialHit:
    material_id: UUID
    title: str
    material_type: str
    root_path: str
    score: float
    snippet: str = ""
    keywords: tuple[str, ...] = ()
    siblings: tuple[str, ...] = ()


@dataclass(frozen=True)
class MaterialUnitInfo:
    unit_type: str
    citation: str


@dataclass(frozen=True)
class MaterialDetail:
    material_id: UUID
    title: str
    material_type: str
    material_subtype: str | None
    root_path: str
    status: str
    summary: str
    purpose: str | None
    keywords: tuple[str, ...]
    topics: tuple[str, ...]
    technologies: tuple[str, ...]
    research_relevance: float | None
    units: tuple[MaterialUnitInfo, ...]


@dataclass(frozen=True)
class MaterialPage:
    results: tuple[MaterialHit, ...]
    has_more: bool
    page_count: int = 0
    total: int = 0


class DeepResearchService:
    def __init__(
        self,
        session: Session,
        index: IndexService,
        store: ObjectStore | None = None,
    ) -> None:
        self._index = index
        self._materials = MaterialRepository(session)
        self._artifacts = ArtifactRepository(session)
        self._store = store

    def search(
        self,
        query: str,
        *,
        offset: int = 0,
        limit: int = 10,
        material_type: str | None = None,
        tracer: object | None = None,
    ) -> MaterialPage:
        log = tracer or _NoopLog()
        if offset < 0:
            raise ValueError("offset must be >= 0")
        if limit < 1:
            raise ValueError("limit must be >= 1")
        with log.span(
            "search", offset=offset, limit=limit, material_type=material_type
        ):
            found = self._index.search_materials(
                query,
                offset=offset,
                limit=limit,
                material_type=material_type,
                tracer=log,
            )
            has_more = offset + len(found.hits) < found.total
            page_count = (
                (found.total + limit - 1) // limit if found.total else 0
            )
            loaded = _load_materials(self._materials, found.hits)
            analyses = self._analyses(
                tuple(hit.entry.material_id for hit in found.hits)
            )
            page = MaterialPage(
                results=tuple(
                    _material_hit(hit, loaded, analyses) for hit in found.hits
                ),
                has_more=has_more,
                page_count=page_count,
                total=found.total,
            )
            log.set_output(
                {
                    "hits": len(page.results),
                    "has_more": page.has_more,
                    "page_count": page.page_count,
                    "total": page.total,
                    "top": page.results[0].title if page.results else None,
                }
            )
            return page

    def get_material(self, material_id: UUID) -> MaterialDetail | None:
        material = self._materials.get(material_id)
        if material is None:
            return None
        analysis = self._analysis_of(material_id)
        research = self._json_of(material_id, "research")
        title = material.name
        summary = ""
        purpose: str | None = None
        keywords: tuple[str, ...] = ()
        topics: tuple[str, ...] = ()
        technologies: tuple[str, ...] = ()
        relevance: float | None = None
        if analysis is not None:
            title = analysis.title or title
            summary = analysis.summary
            purpose = analysis.purpose
            keywords = analysis.keywords
            topics = analysis.topics
            technologies = analysis.technologies
            relevance = analysis.research_relevance
        return MaterialDetail(
            material_id=material.material_id,
            title=title,
            material_type=material.material_type.value,
            material_subtype=material.material_subtype,
            root_path=material.root_path,
            status=material.status.value,
            summary=summary,
            purpose=purpose,
            keywords=keywords,
            topics=topics,
            technologies=technologies,
            research_relevance=relevance,
            units=_unit_infos(research),
        )

    def select(
        self,
        query: str,
        *,
        limit: int = 5,
        material_type: str | None = None,
        tracer: object | None = None,
    ) -> tuple[Citation, ...]:
        log = tracer or _NoopLog()
        detail = self._index.search_detail(
            query, limit=max(limit, 5), material_type=material_type, tracer=log
        )
        hits = tuple(
            hit for hit in detail.ranked if hit.entry.unit_id != MATERIAL_UNIT_ID
        )
        loaded = _load_materials(self._materials, hits)
        with log.span("boost", same_source=_SOURCE_BOOST):
            hits = _boost_same_source(hits, loaded)[:limit]
            log.set_output(
                {
                    "hits": len(hits),
                    "top": format_location(_location(hits[0].entry)) if hits else None,
                    "selected": [
                        {
                            "citation": format_location(_location(item.entry))
                            or item.entry.title,
                            "title": item.entry.title,
                            "material_id": str(item.entry.material_id),
                            "score": round(item.score, 4),
                        }
                        for item in hits
                    ],
                }
            )
        siblings = _siblings_by_source(self._materials, loaded)
        return tuple(_citation(hit, loaded, siblings) for hit in hits)

    def _analyses(
        self, material_ids: tuple[UUID, ...]
    ) -> dict[UUID, MaterialAnalysis]:
        artifacts = self._artifacts.latest_for_ids(material_ids, "analysis")
        found: dict[UUID, MaterialAnalysis] = {}
        for material_id, artifact in artifacts.items():
            payload = _read_json(self._store, artifact.storage_uri)
            analysis = _analysis_from(payload)
            if analysis is not None:
                found[material_id] = analysis
        return found

    def _analysis_of(self, material_id: UUID) -> MaterialAnalysis | None:
        artifact = self._artifacts.latest_of_type(material_id, "analysis")
        if artifact is None:
            return None
        return _analysis_from(_read_json(self._store, artifact.storage_uri))

    def _json_of(self, material_id: UUID, artifact_type: str) -> dict[str, object]:
        artifact = self._artifacts.latest_of_type(material_id, artifact_type)
        if artifact is None:
            return {}
        payload = _read_json(self._store, artifact.storage_uri)
        return payload if payload is not None else {}


def _load_materials(
    repo: MaterialRepository,
    hits: tuple[ScoredEntry, ...],
) -> dict[UUID, Material]:
    found: dict[UUID, Material] = {}
    for hit in hits:
        material_id = hit.entry.material_id
        if material_id in found:
            continue
        material = repo.get(material_id)
        if material is not None:
            found[material_id] = material
    return found


def _boost_same_source(
    hits: tuple[ScoredEntry, ...],
    loaded: dict[UUID, Material],
) -> tuple[ScoredEntry, ...]:
    if not hits:
        return hits
    top = loaded.get(hits[0].entry.material_id)
    if top is None:
        return hits
    boosted: list[ScoredEntry] = []
    for hit in hits:
        material = loaded.get(hit.entry.material_id)
        extra = (
            _SOURCE_BOOST
            if material is not None and material.source_id == top.source_id
            else 0.0
        )
        boosted.append(ScoredEntry(entry=hit.entry, score=hit.score + extra))
    boosted.sort(key=lambda item: item.score, reverse=True)
    return tuple(boosted)


def _location(entry: IndexEntry) -> ContentLocation:
    return ContentLocation(
        path=entry.path,
        page=entry.page,
        line_start=entry.line_start,
        line_end=entry.line_end,
        section=entry.section,
    )


def _material_hit(
    hit: ScoredEntry,
    loaded: dict[UUID, Material],
    analyses: dict[UUID, MaterialAnalysis],
) -> MaterialHit:
    material = loaded.get(hit.entry.material_id)
    analysis = analyses.get(hit.entry.material_id)
    snippet = ""
    keywords: tuple[str, ...] = ()
    if analysis is not None:
        snippet = _snippet(analysis.summary)
        keywords = analysis.keywords[:_MAX_KEYWORDS]
    elif hit.entry.content:
        snippet = _snippet(hit.entry.content)
    return MaterialHit(
        material_id=hit.entry.material_id,
        title=hit.entry.title,
        material_type=(material.material_type.value if material is not None else ""),
        root_path=material.root_path if material is not None else "",
        score=hit.score,
        snippet=snippet,
        keywords=keywords,
    )


def _citation(
    hit: ScoredEntry,
    loaded: dict[UUID, Material],
    siblings: dict[UUID, list[Material]],
) -> Citation:
    location = _location(hit.entry)
    material = loaded.get(hit.entry.material_id)
    return Citation(
        material_id=hit.entry.material_id,
        title=hit.entry.title,
        location=location,
        citation=format_location(location),
        snippet=_snippet(hit.entry.content),
        score=hit.score,
        siblings=_sibling_names(siblings, material),
    )


def _siblings_by_source(
    repo: MaterialRepository, loaded: dict[UUID, Material]
) -> dict[UUID, list[Material]]:
    found: dict[UUID, list[Material]] = {}
    for material in loaded.values():
        source_id = material.source_id
        if source_id in found:
            continue
        found[source_id] = repo.list_for_source(source_id)
    return found


def _sibling_names(
    siblings: dict[UUID, list[Material]], material: Material | None
) -> tuple[str, ...]:
    if material is None:
        return ()
    items = [
        item
        for item in siblings.get(material.source_id, [])
        if item.material_id != material.material_id
        and item.status is MaterialStatus.READY
    ]
    items.sort(
        key=lambda item: (
            _TYPE_ORDER.get(
                item.material_type.value if item.material_type else "",
                9,
            ),
            item.root_path,
        )
    )
    names = [item.root_path for item in items]
    if len(names) <= _MAX_SIBLINGS:
        return tuple(names)
    extra = len(names) - _MAX_SIBLINGS
    return tuple(names[:_MAX_SIBLINGS] + [f"+{extra} more"])


def _snippet(content: str) -> str:
    text = " ".join(content.split())
    if len(text) <= _SNIPPET:
        return text
    return text[: _SNIPPET - 1].rstrip() + "…"


def _read_json(store: ObjectStore | None, uri: str) -> dict[str, object] | None:
    if store is None:
        return None
    try:
        handle = store.open(uri)
    except Exception:
        return None
    try:
        raw = handle.read()
    except Exception:
        return None
    finally:
        handle.close()
    try:
        payload = json.loads(raw)
    except (TypeError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def _analysis_from(payload: dict[str, object] | None) -> MaterialAnalysis | None:
    if payload is None:
        return None
    try:
        return MaterialAnalysis.model_validate(payload)
    except Exception:
        return None


def _unit_infos(research: dict[str, object]) -> tuple[MaterialUnitInfo, ...]:
    raw = research.get("content_units")
    if not isinstance(raw, list):
        return ()
    units: list[MaterialUnitInfo] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        unit_id = item.get("unit_id")
        if unit_id == MATERIAL_UNIT_ID:
            continue
        loc = item.get("location")
        location = ContentLocation()
        if isinstance(loc, dict):
            path = loc.get("path")
            page = loc.get("page")
            line_start = loc.get("line_start")
            line_end = loc.get("line_end")
            section = loc.get("section")
            location = ContentLocation(
                path=path if isinstance(path, str) else None,
                page=page if isinstance(page, int) else None,
                line_start=line_start if isinstance(line_start, int) else None,
                line_end=line_end if isinstance(line_end, int) else None,
                section=section if isinstance(section, str) else None,
            )
        citation = format_location(location)
        unit_type = item.get("type")
        units.append(
            MaterialUnitInfo(
                unit_type=unit_type if isinstance(unit_type, str) else "",
                citation=citation,
            )
        )
    return tuple(units)


class _NoopLog:
    @contextmanager
    def span(self, name: str, **attrs: object) -> Iterator[None]:
        yield

    def set_output(self, value: object) -> None:
        return None
