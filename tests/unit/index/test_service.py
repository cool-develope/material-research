from uuid import uuid4

from tests.unit.helpers.index import make_test_index

from material_platform.domain.enums import MaterialType
from material_platform.domain.research_material import (
    ContentLocation,
    ContentUnit,
    MaterialProvenance,
    ResearchMaterial,
)


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
    assert index.count_for_material(research.material_id) == 2


def test_reprocess_replaces_points() -> None:
    index = make_test_index()
    first = _page("paper.pdf", 1, "alpha topic")
    research = _research(first)
    index.replace(research)
    assert index.count_for_material(research.material_id) == 1
    second = _page("paper.pdf", 1, "alpha topic")
    third = _page("paper.pdf", 2, "beta topic")
    index.replace(research.model_copy(update={"content_units": (second, third)}))
    assert index.count_for_material(research.material_id) == 2
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
    assert index.count_for_material(research.material_id) == 1
    hits = index.search("requests")
    assert hits
    assert hits[0].entry.path == "requests-2.32.3-py3-none-any.whl"
    assert hits[0].entry.page is None
    assert hits[0].entry.line_start is None
