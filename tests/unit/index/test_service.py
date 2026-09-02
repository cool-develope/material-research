from collections.abc import Sequence
from uuid import uuid4

import pytest
from tests.unit.helpers.index import make_test_index

from material_platform.domain.enums import MaterialType
from material_platform.domain.research_material import (
    ContentLocation,
    ContentUnit,
    MaterialProvenance,
    ResearchMaterial,
)
from material_platform.index.payload import MATERIAL_UNIT_ID


def _research(*units: ContentUnit) -> ResearchMaterial:
    return ResearchMaterial(
        material_id=uuid4(),
        material_type=MaterialType.DOCUMENT,
        material_subtype="pdf",
        title="paper.pdf",
        summary="test",
        content_units=units,
        provenance=MaterialProvenance(source_id=uuid4(), root_path="paper.pdf"),
    )


def _page(path: str, page: int, content: str) -> ContentUnit:
    return ContentUnit(
        unit_id=f"{path}:page:{page}",
        type="page",
        content=content,
        location=ContentLocation(path=path, page=page),
        digest="a" * 64,
        metadata={"strategy": "document.pages", "chunk_index": page - 1},
    )


def test_replace_and_search_finds_unique_phrase() -> None:
    index = make_test_index()
    research = _research(
        _page("paper.pdf", 1, "Introduction to materials"),
        _page("paper.pdf", 2, "unique_phrase_page25 appears here"),
    )
    index.replace(research)
    hits = index.search("unique_phrase_page25")
    assert hits
    assert hits[0].entry.path == "paper.pdf"
    assert hits[0].entry.page == 2
    assert index.count_for_material(research.material_id) == 3


def test_reprocess_replaces_points() -> None:
    index = make_test_index()
    first = _page("paper.pdf", 1, "alpha topic")
    research = _research(first)
    index.replace(research)
    assert index.count_for_material(research.material_id) == 2
    second = _page("paper.pdf", 1, "alpha topic")
    third = _page("paper.pdf", 2, "beta topic")
    index.replace(research.model_copy(update={"content_units": (second, third)}))
    assert index.count_for_material(research.material_id) == 3
    hits = index.search("beta topic")
    assert hits[0].entry.page == 2


def test_search_keeps_unique_phrase_with_extra_query_words() -> None:
    index = make_test_index()
    research = _research(
        _page("paper.pdf", 1, "Introduction to materials"),
        _page("paper.pdf", 2, "unique_phrase_page25 appears here"),
    )
    index.replace(research)
    hits = index.search("where is unique_phrase_page25 discussed")
    assert hits
    assert hits[0].entry.page == 2


def test_replace_wheel_keeps_one_point() -> None:
    index = make_test_index()
    research = ResearchMaterial(
        material_id=uuid4(),
        material_type=MaterialType.CODE,
        material_subtype="python_wheel",
        title="requests-2.32.3-py3-none-any.whl",
        summary="requests",
        content_units=(
            ContentUnit(
                unit_id="artifact",
                type="artifact",
                content="package requests version 2.32.3",
                location=ContentLocation(path="requests-2.32.3-py3-none-any.whl"),
                digest="b" * 64,
                metadata={"strategy": "artifact.identity"},
            ),
        ),
        provenance=MaterialProvenance(
            source_id=uuid4(),
            root_path="requests-2.32.3-py3-none-any.whl",
        ),
        metadata={"package": "requests", "version": "2.32.3"},
    )
    index.replace(research)
    assert index.count_for_material(research.material_id) == 2
    hits = index.search("requests")
    assert hits
    assert hits[0].entry.path == "requests-2.32.3-py3-none-any.whl"
    assert hits[0].entry.page is None
    assert hits[0].entry.line_start is None
    assert hits[0].entry.unit_id != MATERIAL_UNIT_ID


def test_replace_two_pages_is_three_points() -> None:
    index = make_test_index()
    research = _research(
        _page("paper.pdf", 1, "Introduction to materials"),
        _page("paper.pdf", 2, "methods section"),
    )
    index.replace(research)
    assert index.count_for_material(research.material_id) == 3
    index.replace(research)
    assert index.count_for_material(research.material_id) == 3
    hits = index.search("Introduction to materials")
    assert hits
    assert all(hit.entry.unit_id != MATERIAL_UNIT_ID for hit in hits)
    assert hits[0].entry.page == 1


def test_search_routes_keyword_query_to_material_units() -> None:
    index = make_test_index()
    target = _research(_page("paper.pdf", 1, "Introduction to materials"))
    target = target.model_copy(
        update={"metadata": {"keywords": ["aerospace_alloys_topic"]}}
    )
    distractor = ResearchMaterial(
        material_id=uuid4(),
        material_type=MaterialType.DOCUMENT,
        material_subtype="pdf",
        title="noise.pdf",
        summary="unrelated notes",
        content_units=(_page("noise.pdf", 1, "aerospace_alloys_topic " * 40),),
        provenance=MaterialProvenance(source_id=uuid4(), root_path="noise.pdf"),
    )
    index.replace(target)
    index.replace(distractor)
    for index_no in range(6):
        filler = ResearchMaterial(
            material_id=uuid4(),
            material_type=MaterialType.DOCUMENT,
            material_subtype="pdf",
            title=f"filler{index_no}.pdf",
            summary="other notes",
            content_units=(
                _page(f"filler{index_no}.pdf", 1, f"background filler {index_no}"),
            ),
            provenance=MaterialProvenance(
                source_id=uuid4(), root_path=f"filler{index_no}.pdf"
            ),
        )
        index.replace(filler)
    detail = index.search_detail("aerospace_alloys_topic")
    hop1_titles = {hit.entry.title for hit in detail.hop1}
    assert "paper.pdf" in hop1_titles
    assert "noise.pdf" not in hop1_titles
    assert all(hit.entry.path != "noise.pdf" for hit in detail.hop2)
    assert any(hit.entry.path == "paper.pdf" for hit in detail.hop2)
    assert all(hit.entry.unit_id != MATERIAL_UNIT_ID for hit in detail.ranked)


def test_search_materials_returns_material_points() -> None:
    index = make_test_index()
    target = _research(_page("paper.pdf", 1, "Introduction to materials"))
    target = target.model_copy(
        update={"metadata": {"keywords": ["aerospace_alloys_topic"]}}
    )
    distractor = ResearchMaterial(
        material_id=uuid4(),
        material_type=MaterialType.DOCUMENT,
        material_subtype="pdf",
        title="noise.pdf",
        summary="unrelated notes",
        content_units=(_page("noise.pdf", 1, "aerospace_alloys_topic " * 40),),
        provenance=MaterialProvenance(source_id=uuid4(), root_path="noise.pdf"),
    )
    index.replace(target)
    index.replace(distractor)
    hits = index.search_materials("aerospace_alloys_topic")
    assert hits
    assert all(hit.entry.unit_id == MATERIAL_UNIT_ID for hit in hits)
    assert hits[0].entry.title == "paper.pdf"
    assert all(hit.entry.path is None for hit in hits)


def test_search_materials_paginates() -> None:
    index = make_test_index()
    for index_no in range(5):
        research = ResearchMaterial(
            material_id=uuid4(),
            material_type=MaterialType.DOCUMENT,
            material_subtype="pdf",
            title=f"paper{index_no}.pdf",
            summary="notes",
            content_units=(
                _page(f"paper{index_no}.pdf", 1, f"shared topic {index_no}"),
            ),
            provenance=MaterialProvenance(
                source_id=uuid4(), root_path=f"paper{index_no}.pdf"
            ),
        )
        index.replace(research)
    first = index.search_materials("shared topic", offset=0, limit=2)
    second = index.search_materials("shared topic", offset=2, limit=2)
    assert len(first) == 2
    assert len(second) == 2
    first_ids = {hit.entry.material_id for hit in first}
    second_ids = {hit.entry.material_id for hit in second}
    assert first_ids.isdisjoint(second_ids)


def test_search_materials_filters_by_material_type() -> None:
    index = make_test_index()
    paper = _research(_page("paper.pdf", 1, "def handle_request is discussed"))
    backend = ResearchMaterial(
        material_id=uuid4(),
        material_type=MaterialType.PROJECT,
        material_subtype="python",
        title="backend",
        summary="REST handler",
        content_units=(
            ContentUnit(
                unit_id="src/api.py",
                type="file",
                content="def handle_request():\n    return 'ok'\n",
                location=ContentLocation(path="src/api.py", line_start=1, line_end=2),
                digest="c" * 64,
                metadata={"strategy": "code.file", "chunk_index": 0},
            ),
        ),
        provenance=MaterialProvenance(source_id=uuid4(), root_path="backend/"),
    )
    index.replace(paper)
    index.replace(backend)
    project_hits = index.search_materials("handle_request", material_type="project")
    assert project_hits
    assert all(hit.entry.unit_id == MATERIAL_UNIT_ID for hit in project_hits)
    assert project_hits[0].entry.title == "backend"
    document_hits = index.search_materials("handle_request", material_type="document")
    assert document_hits
    assert document_hits[0].entry.title == "paper.pdf"


def test_search_falls_back_without_material_points() -> None:
    from qdrant_client import QdrantClient

    from material_platform.index.payload import make_point, unit_text
    from material_platform.index.service import IndexService
    from material_platform.infrastructure.embedding.fake import FakeEmbedder
    from material_platform.infrastructure.qdrant.store import QdrantIndexStore

    embedder = FakeEmbedder()
    store = QdrantIndexStore(QdrantClient(":memory:"), "research")
    index = IndexService(store, embedder)
    research = _research(_page("paper.pdf", 1, "unique_phrase_page25 appears here"))
    unit = research.content_units[0]
    store.replace(
        research.material_id,
        [make_point(research, unit, embedder.embed(unit_text(research, unit)))],
    )
    hits = index.search("unique_phrase_page25")
    assert hits
    assert hits[0].entry.page == 1
    assert hits[0].entry.unit_id != MATERIAL_UNIT_ID


def test_search_filters_by_material_type() -> None:
    index = make_test_index()
    paper = _research(_page("paper.pdf", 1, "def handle_request is discussed"))
    backend = ResearchMaterial(
        material_id=uuid4(),
        material_type=MaterialType.PROJECT,
        material_subtype="python",
        title="backend",
        summary="REST handler",
        content_units=(
            ContentUnit(
                unit_id="src/api.py",
                type="file",
                content="def handle_request():\n    return 'ok'\n",
                location=ContentLocation(path="src/api.py", line_start=1, line_end=2),
                digest="c" * 64,
                metadata={"strategy": "code.file", "chunk_index": 0},
            ),
        ),
        provenance=MaterialProvenance(source_id=uuid4(), root_path="backend/"),
    )
    index.replace(paper)
    index.replace(backend)
    project_hits = index.search("handle_request", material_type="project")
    assert project_hits
    assert project_hits[0].entry.path == "src/api.py"
    document_hits = index.search("handle_request", material_type="document")
    assert document_hits
    assert document_hits[0].entry.path == "paper.pdf"


def test_search_rejects_unknown_material_type() -> None:
    index = make_test_index()
    with pytest.raises(ValueError, match="material_type"):
        index.search("hello", material_type="widget")


class _PreferBackoff:
    def score(self, query: str, texts: Sequence[str]) -> tuple[float, ...]:
        return tuple(1.0 if "backoff" in text else 0.0 for text in texts)


def test_reranker_reorders_hop2() -> None:
    index = make_test_index(_PreferBackoff())
    research = _research(
        _page("paper.pdf", 1, "alpha shared filler"),
        _page("paper.pdf", 2, "alpha shared backoff"),
    )
    index.replace(research)
    hits = index.search("alpha")
    assert hits
    assert hits[0].entry.page == 2
    detail = index.search_detail("alpha")
    assert detail.reranked
    assert len(detail.hop2) == len(detail.ranked)
    assert detail.ranked[0].entry.page == 2


def test_search_detail_caps_hop2_at_unit_hop() -> None:
    from material_platform.index.service import UNIT_HOP

    index = make_test_index()
    units = tuple(
        _page("paper.pdf", page, f"alpha shared page {page}")
        for page in range(1, UNIT_HOP + 8)
    )
    index.replace(_research(*units))
    detail = index.search_detail("alpha", limit=50)
    assert len(detail.hop2) <= UNIT_HOP
    assert len(detail.ranked) <= UNIT_HOP


def test_wipe_drops_all_points() -> None:
    index = make_test_index()
    index.replace(_research(_page("paper.pdf", 1, "unique_wipe_phrase")))
    assert index.search("unique_wipe_phrase")
    index.wipe()
    assert index.search("unique_wipe_phrase") == ()


def test_unit_text_is_unit_body_not_analysis() -> None:
    from material_platform.index.payload import material_text, unit_text

    unit = _page("paper.pdf", 1, "page body about annealing")
    research = _research(unit).model_copy(
        update={
            "title": "LLM Headline About Quantum Widgets",
            "summary": "llm_summary_should_not_embed",
            "metadata": {"keywords": ["grounded_keyword"], "topics": ["annealing"]},
        }
    )
    text = unit_text(research, unit)
    assert "page body about annealing" in text
    assert "LLM Headline About Quantum Widgets" not in text
    assert "llm_summary_should_not_embed" not in text
    card = material_text(research)
    assert card.startswith("paper.pdf")
    assert "grounded_keyword" in card
    assert "annealing" in card
    assert "LLM Headline About Quantum Widgets" not in card
    assert "llm_summary_should_not_embed" not in card
