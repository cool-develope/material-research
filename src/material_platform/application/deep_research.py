from uuid import UUID

from sqlalchemy.orm import Session

from material_platform.agent.trace import NoOpTracer, Tracer
from material_platform.application.tree import format_location
from material_platform.domain.citation import Citation
from material_platform.domain.enums import MaterialStatus
from material_platform.domain.index_entry import IndexEntry
from material_platform.domain.material import Material
from material_platform.domain.research_material import ContentLocation
from material_platform.index import IndexService
from material_platform.index.payload import MATERIAL_UNIT_ID
from material_platform.index.service import ScoredEntry
from material_platform.infrastructure.database.repositories import MaterialRepository

_SNIPPET = 160
_SOURCE_BOOST = 0.05
_MAX_SIBLINGS = 4
_TYPE_ORDER = {
    "document": 0,
    "project": 1,
    "dataset": 2,
    "code": 3,
}


class DeepResearchService:
    def __init__(self, session: Session, index: IndexService) -> None:
        self._index = index
        self._materials = MaterialRepository(session)

    def select(
        self,
        query: str,
        *,
        limit: int = 5,
        material_type: str | None = None,
        tracer: Tracer | None = None,
    ) -> tuple[Citation, ...]:
        log = tracer or NoOpTracer()
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
                }
            )
        return tuple(_citation(hit, loaded, self._materials) for hit in hits)


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


def _citation(
    hit: ScoredEntry,
    loaded: dict[UUID, Material],
    repo: MaterialRepository,
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
        siblings=_siblings(repo, material),
    )


def _siblings(repo: MaterialRepository, material: Material | None) -> tuple[str, ...]:
    if material is None:
        return ()
    items = [
        item
        for item in repo.list_for_source(material.source_id)
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
