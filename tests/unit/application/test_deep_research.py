from pathlib import Path

from sqlalchemy.orm import Session

from material_platform.analysis import ANALYZER, ANALYZER_VERSION
from material_platform.application.deep_research import DeepResearchService
from material_platform.application.ingest_source import IngestSourceService
from material_platform.application.process_material import ProcessMaterialService
from material_platform.discovery.archive import ArchiveLimits
from material_platform.index import INDEX_VERSION
from material_platform.infrastructure.database.repositories import IndexRepository
from material_platform.infrastructure.object_store import (
    FilesystemObjectStore,
    material_artifact,
)
from material_platform.infrastructure.workspace import TemporaryWorkspace
from tests.unit.discovery.trees import make_go_project, make_mixed_tree, zip_contents
from tests.unit.helpers.pdf import build_text_pdf
from tests.unit.helpers.text import numbered_words


def _ingest_and_process(session: Session, tmp_path: Path) -> None:
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
    processor = ProcessMaterialService(session, store)
    for material in ingested.materials:
        processor.process(material)
    session.flush()


def test_deep_research_cites_pdf_page_and_api_lines(
    session: Session,
    tmp_path: Path,
) -> None:
    _ingest_and_process(session, tmp_path)
    research = DeepResearchService(session)

    pages = research.select("Introduction to materials")
    assert pages
    assert any(
        "paper.pdf" in hit.citation and "page 1" in hit.citation for hit in pages
    )

    lines = research.select("handle_request")
    assert lines
    assert any(
        "src/api.py" in hit.citation and "lines " in hit.citation for hit in lines
    )


def test_select_cites_late_pdf_page(
    session: Session,
    tmp_path: Path,
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
    ProcessMaterialService(session, store).process(ingested.materials[0])
    session.flush()

    hits = DeepResearchService(session).select("unique_phrase_page25")
    assert hits
    assert any(
        "paper.pdf" in hit.citation and "page 25" in hit.citation for hit in hits
    )


def test_select_lists_same_source_siblings(
    session: Session,
    tmp_path: Path,
) -> None:
    _ingest_and_process(session, tmp_path)
    hits = DeepResearchService(session).select("Introduction to materials")
    assert hits
    paper = next(hit for hit in hits if "paper.pdf" in hit.citation)
    assert "backend/" in paper.siblings
    assert "dataset/" in paper.siblings
    assert "paper.pdf" not in paper.siblings


def test_reprocess_replaces_index_entries(
    session: Session,
    tmp_path: Path,
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
    processor = ProcessMaterialService(session, store)
    first = processor.process(paper)
    session.flush()
    index = IndexRepository(session)
    count = len(index.list_for_material(paper.material_id, INDEX_VERSION))
    assert count >= 1
    assert store.exists(
        material_artifact(paper.material_id, "analysis", ANALYZER_VERSION)
    )
    assert first.analysis.analyzer == ANALYZER

    processor.process(first.material)
    session.flush()
    again = index.list_for_material(paper.material_id, INDEX_VERSION)
    assert len(again) == count


def test_deep_research_cites_go_source_lines(
    session: Session,
    tmp_path: Path,
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
    ProcessMaterialService(session, store).process(ingested.materials[0])
    session.flush()

    hits = DeepResearchService(session).select("HandleRequest")
    assert hits
    assert any(
        "main.go" in hit.citation and "lines " in hit.citation for hit in hits
    )


def test_select_finds_tail_of_10k_token_document(
    session: Session,
    tmp_path: Path,
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
    processed = ProcessMaterialService(session, store).process(ingested.materials[0])
    session.flush()
    assert len(processed.research.content_units) > 20
    assert all(
        unit.metadata.get("strategy") == "document.window"
        for unit in processed.research.content_units
    )

    hits = DeepResearchService(session).select("tok11999")
    assert hits
    assert any(
        "paper.txt" in hit.citation and "lines " in hit.citation for hit in hits
    )
