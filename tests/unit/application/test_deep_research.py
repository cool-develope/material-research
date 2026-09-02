from pathlib import Path

from sqlalchemy.orm import Session

from material_platform.agent.trace import RecordingTracer
from material_platform.analysis import ANALYZER, ANALYZER_VERSION
from material_platform.application.deep_research import DeepResearchService
from material_platform.application.ingest_source import IngestSourceService
from material_platform.application.process_material import ProcessMaterialService
from material_platform.discovery.archive import ArchiveLimits
from material_platform.index import IndexService
from material_platform.infrastructure.object_store import (
    FilesystemObjectStore,
    material_artifact,
)
from material_platform.infrastructure.workspace import TemporaryWorkspace
from tests.unit.discovery.artifacts import write_wheel
from tests.unit.discovery.trees import (
    FIXTURE_ZIP,
    make_go_project,
    make_mixed_tree,
    zip_contents,
)
from tests.unit.helpers.pdf import build_text_pdf
from tests.unit.helpers.text import numbered_words


def _ingest_and_process(session: Session, tmp_path: Path, index: IndexService) -> None:
    mixed = make_mixed_tree(tmp_path / "mixed")
    archive = zip_contents(mixed, tmp_path / "research.zip")
    store = FilesystemObjectStore(tmp_path / "store")
    workspace = TemporaryWorkspace(tmp_path / "work")
    ingested = IngestSourceService.create(
        session,
        store,
        workspace,
        discovery_version="boundary-v1",
        max_archive_depth=5,
        archive_limits=ArchiveLimits(),
    ).ingest(archive)
    session.flush()
    processor = ProcessMaterialService(session, store, index=index)
    for material in ingested.materials:
        processor.process(material)
    session.flush()


def test_deep_research_cites_pdf_page_and_api_lines(
    session: Session,
    tmp_path: Path,
    index: IndexService,
) -> None:
    _ingest_and_process(session, tmp_path, index)
    research = DeepResearchService(session, index)

    pages = research.select("Introduction to materials")
    assert pages
    assert any(
        "paper.pdf" in hit.citation and "page 1" in hit.citation for hit in pages
    )

    lines = research.select("handle_request")
    assert lines
    assert "src/api.py" in lines[0].citation
    assert "lines " in lines[0].citation
    assert all("__material__" not in hit.citation for hit in pages)
    assert all("__material__" not in hit.citation for hit in lines)


def test_select_traces_hop1_hop2_rerank(
    session: Session,
    tmp_path: Path,
    index: IndexService,
) -> None:
    _ingest_and_process(session, tmp_path, index)
    tracer = RecordingTracer()
    hits = DeepResearchService(session, index).select("handle_request", tracer=tracer)
    assert hits
    names = [span.name for span in tracer.spans]
    assert names == ["embed", "hop1", "hop2", "rerank", "boost"]
    hop1 = next(span for span in tracer.spans if span.name == "hop1")
    hop2 = next(span for span in tracer.spans if span.name == "hop2")
    rerank = next(span for span in tracer.spans if span.name == "rerank")
    embed = next(span for span in tracer.spans if span.name == "embed")
    assert hop1.attrs["k"] == 5
    assert hop1.attrs["level"] == "material"
    embed_out = embed.attrs["output"]
    assert isinstance(embed_out, dict)
    assert embed_out["model"] == "fake"
    assert embed_out["chars"] > 0
    hop1_out = hop1.attrs["output"]
    assert isinstance(hop1_out, dict)
    assert isinstance(hop1_out["hits"], int)
    assert hop1_out["hits"] >= 1
    assert hop1_out["top"]
    hop2_out = hop2.attrs["output"]
    assert isinstance(hop2_out, dict)
    assert "src/api.py" in str(hop2_out["top"])
    rerank_out = rerank.attrs["output"]
    assert isinstance(rerank_out, dict)
    assert rerank_out["enabled"] is False
    assert rerank_out["docs"] >= 1
    assert "before" not in rerank_out
    assert "after" not in rerank_out


def test_select_filters_by_material_type(
    session: Session,
    tmp_path: Path,
    index: IndexService,
) -> None:
    _ingest_and_process(session, tmp_path, index)
    research = DeepResearchService(session, index)
    projects = research.select("handle_request", material_type="project")
    assert projects
    assert "src/api.py" in projects[0].citation
    documents = research.select("handle_request", material_type="document")
    assert all("src/api.py" not in hit.citation for hit in documents)


def test_select_cites_late_pdf_page(
    session: Session,
    tmp_path: Path,
    index: IndexService,
) -> None:
    pages = [f"filler page {index}" for index in range(1, 25)]
    pages.append("unique_phrase_page25 appears here")
    pdf = tmp_path / "paper.pdf"
    pdf.write_bytes(build_text_pdf(pages))
    store = FilesystemObjectStore(tmp_path / "store")
    workspace = TemporaryWorkspace(tmp_path / "work")
    ingested = IngestSourceService.create(
        session,
        store,
        workspace,
        discovery_version="boundary-v1",
        max_archive_depth=5,
        archive_limits=ArchiveLimits(),
    ).ingest(pdf)
    session.flush()
    ProcessMaterialService(session, store, index=index).process(ingested.materials[0])
    session.flush()

    hits = DeepResearchService(session, index).select("unique_phrase_page25")
    assert hits
    assert "page 25" in hits[0].citation


def test_select_lists_same_source_siblings(
    session: Session,
    tmp_path: Path,
    index: IndexService,
) -> None:
    _ingest_and_process(session, tmp_path, index)
    hits = DeepResearchService(session, index).select("Introduction to materials")
    assert hits
    paper = next(hit for hit in hits if "paper.pdf" in hit.citation)
    assert "backend/" in paper.siblings
    assert "dataset/" in paper.siblings
    assert "paper.pdf" not in paper.siblings


def test_reprocess_replaces_index_entries(
    session: Session,
    tmp_path: Path,
    index: IndexService,
) -> None:
    mixed = make_mixed_tree(tmp_path / "mixed")
    archive = zip_contents(mixed, tmp_path / "research.zip")
    store = FilesystemObjectStore(tmp_path / "store")
    workspace = TemporaryWorkspace(tmp_path / "work")
    ingested = IngestSourceService.create(
        session,
        store,
        workspace,
        discovery_version="boundary-v1",
        max_archive_depth=5,
        archive_limits=ArchiveLimits(),
    ).ingest(archive)
    session.flush()
    paper = next(item for item in ingested.materials if item.root_path == "paper.pdf")
    processor = ProcessMaterialService(session, store, index=index)
    first = processor.process(paper)
    session.flush()
    count = index.count_for_material(paper.material_id)
    assert count >= 1
    assert store.exists(
        material_artifact(paper.material_id, "analysis", ANALYZER_VERSION)
    )
    assert first.analysis.analyzer == ANALYZER

    processor.process(first.material)
    session.flush()
    assert index.count_for_material(paper.material_id) == count


def test_deep_research_cites_go_source_lines(
    session: Session,
    tmp_path: Path,
    index: IndexService,
) -> None:
    project = make_go_project(tmp_path / "tools")
    store = FilesystemObjectStore(tmp_path / "store")
    workspace = TemporaryWorkspace(tmp_path / "work")
    ingested = IngestSourceService.create(
        session,
        store,
        workspace,
        discovery_version="boundary-v1",
        max_archive_depth=5,
        archive_limits=ArchiveLimits(),
    ).ingest(project)
    session.flush()
    ProcessMaterialService(session, store, index=index).process(ingested.materials[0])
    session.flush()

    hits = DeepResearchService(session, index).select("HandleRequest")
    assert hits
    assert any("main.go" in hit.citation and "lines " in hit.citation for hit in hits)


def test_select_cites_wheel_filename(
    session: Session,
    tmp_path: Path,
    index: IndexService,
) -> None:
    wheel = write_wheel(tmp_path / "requests-2.32.3-py3-none-any.whl")
    store = FilesystemObjectStore(tmp_path / "store")
    workspace = TemporaryWorkspace(tmp_path / "work")
    ingested = IngestSourceService.create(
        session,
        store,
        workspace,
        discovery_version="boundary-v1",
        max_archive_depth=5,
        archive_limits=ArchiveLimits(),
    ).ingest(wheel)
    session.flush()
    processed = ProcessMaterialService(session, store, index=index).process(
        ingested.materials[0]
    )
    session.flush()
    assert index.count_for_material(processed.material.material_id) == 2

    hits = DeepResearchService(session, index).select("requests")
    assert hits
    assert hits[0].citation == "requests-2.32.3-py3-none-any.whl"


def test_select_finds_tail_of_10k_token_document(
    session: Session,
    tmp_path: Path,
    index: IndexService,
) -> None:
    notes = tmp_path / "paper.txt"
    notes.write_text(numbered_words(12_000, "tok"))
    store = FilesystemObjectStore(tmp_path / "store")
    workspace = TemporaryWorkspace(tmp_path / "work")
    ingested = IngestSourceService.create(
        session,
        store,
        workspace,
        discovery_version="boundary-v1",
        max_archive_depth=5,
        archive_limits=ArchiveLimits(),
    ).ingest(notes)
    session.flush()
    processed = ProcessMaterialService(session, store, index=index).process(
        ingested.materials[0]
    )
    session.flush()
    assert len(processed.research.content_units) > 20
    assert all(
        unit.metadata.get("strategy") == "document.window"
        for unit in processed.research.content_units
    )

    hits = DeepResearchService(session, index).select("tok11999")
    assert hits
    top = hits[0]
    assert "paper.txt" in top.citation
    assert "lines " in top.citation
    assert top.location.line_end is not None
    assert top.location.line_end >= 700
    assert all("paper.txt" in hit.citation for hit in hits)


def test_select_caps_sibling_list(
    session: Session,
    tmp_path: Path,
    index: IndexService,
) -> None:
    store = FilesystemObjectStore(tmp_path / "store")
    workspace = TemporaryWorkspace(tmp_path / "work")
    ingested = IngestSourceService.create(
        session,
        store,
        workspace,
        discovery_version="boundary-v1",
        max_archive_depth=5,
        archive_limits=ArchiveLimits(),
    ).ingest(FIXTURE_ZIP)
    session.flush()
    processor = ProcessMaterialService(session, store, index=index)
    for material in ingested.materials:
        processor.process(material)
    session.flush()

    hits = DeepResearchService(session, index).select("Survey of materials")
    assert hits
    paper = next(hit for hit in hits if "survey.pdf" in hit.citation)
    assert any(
        item.startswith("+") and item.endswith("more") for item in paper.siblings
    )
    assert len(paper.siblings) == 5
