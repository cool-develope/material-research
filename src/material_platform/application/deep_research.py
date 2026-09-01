from sqlalchemy.orm import Session

from material_platform.application.tree import format_location
from material_platform.domain.citation import Citation
from material_platform.domain.research_material import ContentLocation
from material_platform.index import IndexService
from material_platform.index.service import ScoredEntry

_SNIPPET = 160


class DeepResearchService:
    def __init__(self, session: Session) -> None:
        self._index = IndexService(session)

    def select(self, query: str, *, limit: int = 5) -> tuple[Citation, ...]:
        return tuple(_citation(hit) for hit in self._index.search(query, limit=limit))


def _citation(hit: ScoredEntry) -> Citation:
    location = ContentLocation(
        path=hit.entry.path,
        page=hit.entry.page,
        line_start=hit.entry.line_start,
        line_end=hit.entry.line_end,
        section=hit.entry.section,
    )
    return Citation(
        material_id=hit.entry.material_id,
        title=hit.entry.title,
        location=location,
        citation=format_location(location),
        snippet=_snippet(hit.entry.content),
        score=hit.score,
    )


def _snippet(content: str) -> str:
    text = " ".join(content.split())
    if len(text) <= _SNIPPET:
        return text
    return text[: _SNIPPET - 1].rstrip() + "…"
