from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from sqlalchemy.orm import Session

from material_platform.domain.index_entry import IndexEntry
from material_platform.domain.research_material import ContentUnit, ResearchMaterial
from material_platform.index.tokens import combined_score, embed, tokenize
from material_platform.infrastructure.database.repositories import IndexRepository

INDEX_VERSION = "v1"


@dataclass(frozen=True)
class ScoredEntry:
    entry: IndexEntry
    score: float


class IndexService:
    def __init__(self, session: Session) -> None:
        self._entries = IndexRepository(session)

    def replace(self, research: ResearchMaterial) -> None:
        entries = tuple(_entry(research, unit) for unit in research.content_units)
        self._entries.replace_material(
            research.material_id,
            INDEX_VERSION,
            entries,
        )

    def search(self, query: str, *, limit: int = 5) -> tuple[ScoredEntry, ...]:
        query_tokens = tokenize(query)
        if not query_tokens:
            return ()
        query_vector = embed(query_tokens)
        scored: list[ScoredEntry] = []
        for entry in self._entries.list_current(INDEX_VERSION):
            document_tokens = tuple(entry.tokens.split()) if entry.tokens else ()
            score = combined_score(
                query_tokens,
                query_vector,
                document_tokens,
                entry.embedding,
            )
            if score > 0:
                scored.append(ScoredEntry(entry=entry, score=score))
        scored.sort(key=lambda item: item.score, reverse=True)
        return tuple(scored[:limit])


def _entry(research: ResearchMaterial, unit: ContentUnit) -> IndexEntry:
    tokens = tokenize(f"{research.title} {unit.content}")
    location = unit.location
    return IndexEntry(
        entry_id=uuid4(),
        material_id=research.material_id,
        unit_id=unit.unit_id,
        index_version=INDEX_VERSION,
        title=research.title,
        content=unit.content,
        path=location.path,
        page=location.page,
        line_start=location.line_start,
        line_end=location.line_end,
        section=location.section,
        tokens=" ".join(tokens),
        embedding=embed(tokens),
    )
