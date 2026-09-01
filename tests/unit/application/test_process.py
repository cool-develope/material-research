from io import BytesIO
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from material_platform.analysis import ANALYZER, ANALYZER_VERSION
from material_platform.application import ProcessMaterialService
from material_platform.application.ingest_source import IngestSourceService
from material_platform.discovery.archive import ArchiveLimits
from material_platform.domain.enums import MaterialStatus, MaterialType
from material_platform.infrastructure.database.repositories import (
    ArtifactRepository,
    ClassificationRepository,
    MaterialRepository,
)
from material_platform.infrastructure.object_store import (
    FilesystemObjectStore,
    material_artifact,
    material_content,
)
from material_platform.infrastructure.workspace import TemporaryWorkspace
from material_platform.research import RESEARCH_VERSION
from tests.unit.discovery.artifacts import write_docx, write_jar, write_pe, write_wheel
from tests.unit.discovery.trees import (
    make_dataset,
    make_go_project,
    make_mixed_tree,
    make_nested_lab_data,
    make_python_project,
    zip_contents,
)
from tests.unit.helpers.pdf import build_text_pdf


def _ingest(session: Session, tmp_path: Path, source_path: Path):
    store = FilesystemObjectStore(tmp_path / "store")
    workspace = TemporaryWorkspace(tmp_path / "work")
    service = IngestSourceService.create(
        session,
        store,
        workspace,
        discovery_version="boundary-v1",
        max_archive_depth=5,
        archive_limits=ArchiveLimits(),
    )
    result = service.ingest(source_path)
    session.flush()
    return result, store


def test_process_pdf_produces_page_locations(
    session: Session,
    tmp_path: Path,
) -> None:
    pdf = tmp_path / "paper.pdf"
    pdf.write_bytes(build_text_pdf(["Introduction to materials"]))
    ingested, store = _ingest(session, tmp_path, pdf)
    material = ingested.materials[0]

    processed = ProcessMaterialService(session, store).process(material)
    session.flush()

    assert processed.material.status is MaterialStatus.READY
    assert processed.research.material_type is MaterialType.DOCUMENT
    assert processed.research.content_units[0].location.page == 1
    assert "Introduction" in processed.research.content_units[0].content
    assert processed.research.provenance.root_path == "paper.pdf"
    assert processed.analysis.analyzer == ANALYZER
    assert store.exists(
        material_artifact(material.material_id, "research", RESEARCH_VERSION)
    )
    assert store.exists(
        material_artifact(material.material_id, "analysis", ANALYZER_VERSION)
    )


def test_process_python_project_produces_line_ranges(
    session: Session,
    tmp_path: Path,
) -> None:
    project = make_python_project(tmp_path / "backend")
    ingested, store = _ingest(session, tmp_path, project)
    material = ingested.materials[0]

    processed = ProcessMaterialService(session, store).process(material)
    session.flush()

    assert processed.classification.material_type is MaterialType.PROJECT
    assert processed.classification.subtype == "python"
    locations = {
        (unit.location.path, unit.location.line_start, unit.location.line_end)
        for unit in processed.research.content_units
    }
    assert ("src/main.py", 1, 1) in locations
    assert ("src/api.py", 1, 2) in locations
    assert any(path == "pyproject.toml" for path, _start, _end in locations)

    latest = ClassificationRepository(session).get_latest(material.material_id)
    assert latest is not None
    assert latest.classifier == "deterministic"


def test_process_csv_dataset_produces_table_unit(
    session: Session,
    tmp_path: Path,
) -> None:
    dataset = make_dataset(tmp_path / "dataset")
    ingested, store = _ingest(session, tmp_path, dataset)
    processed = ProcessMaterialService(session, store).process(ingested.materials[0])

    assert processed.research.material_type is MaterialType.DATASET
    unit = processed.research.content_units[0]
    assert unit.type == "table"
    assert unit.location.line_start == 1
    assert unit.location.line_end == 2


def test_reprocess_does_not_duplicate_classification(
    session: Session,
    tmp_path: Path,
) -> None:
    pdf = tmp_path / "paper.pdf"
    pdf.write_bytes(build_text_pdf(["Hello"]))
    ingested, store = _ingest(session, tmp_path, pdf)
    processor = ProcessMaterialService(session, store)
    first = processor.process(ingested.materials[0])
    session.flush()
    second = processor.process(first.material)
    session.flush()

    assert (
        first.classification.classification_id
        == second.classification.classification_id
    )
    artifacts = ArtifactRepository(session)
    research = artifacts.get_by_identity(
        first.material.material_id,
        "research",
        "research-builder",
        RESEARCH_VERSION,
    )
    assert research is not None


def test_failed_material_retries_alone_siblings_stay_ready(
    session: Session,
    tmp_path: Path,
) -> None:
    mixed = make_mixed_tree(tmp_path / "mixed")
    archive = zip_contents(mixed, tmp_path / "research.zip")
    ingested, store = _ingest(session, tmp_path, archive)
    processor = ProcessMaterialService(session, store)
    by_path = {item.root_path: item for item in ingested.materials}

    backend = processor.process(by_path["backend/"])
    dataset = processor.process(by_path["dataset/"])
    session.flush()
    assert backend.material.status is MaterialStatus.READY
    assert dataset.material.status is MaterialStatus.READY

    paper = by_path["paper.pdf"]
    content = tmp_path / "store" / material_content(paper.material_id, "paper.pdf")
    original = content.read_bytes()
    content.unlink()

    with pytest.raises(Exception):
        processor.process(paper)
    session.flush()

    materials = MaterialRepository(session)
    failed = materials.get(paper.material_id)
    backend_row = materials.get(backend.material.material_id)
    dataset_row = materials.get(dataset.material.material_id)
    assert failed is not None and failed.status is MaterialStatus.FAILED
    assert backend_row is not None and backend_row.status is MaterialStatus.READY
    assert dataset_row is not None and dataset_row.status is MaterialStatus.READY

    store.put(
        uri=material_content(paper.material_id, "paper.pdf"),
        data=BytesIO(original),
        size=len(original),
    )
    retried = processor.process(paper)
    session.flush()

    assert retried.material.status is MaterialStatus.READY
    assert retried.research.content_units[0].location.page == 1
    assert materials.get(backend.material.material_id).status is MaterialStatus.READY
    assert materials.get(dataset.material.material_id).status is MaterialStatus.READY
    assert materials.get(backend.material.material_id).material_id == (
        backend.material.material_id
    )


def test_process_mixed_archive_with_artifacts_all_ready(
    session: Session,
    tmp_path: Path,
) -> None:
    mixed = make_mixed_tree(tmp_path / "mixed")
    write_pe(mixed / "AndroidStudio-setup.exe")
    write_wheel(mixed / "requests-2.32.3-py3-none-any.whl")
    write_jar(mixed / "guava.jar")
    write_docx(mixed / "notes.docx")
    archive = zip_contents(mixed, tmp_path / "research.zip")
    ingested, store = _ingest(session, tmp_path, archive)
    by_path = {item.root_path: item for item in ingested.materials}

    assert "AndroidStudio-setup.exe" in by_path
    assert "notes.docx" in by_path
    wheel = next(item for item in ingested.materials if item.root_path.endswith(".whl"))
    jar = next(item for item in ingested.materials if item.root_path.endswith(".jar"))
    assert wheel.name.startswith("requests")
    assert jar.name.startswith("guava")
    assert not any(".class" in item.root_path for item in ingested.materials)
    assert not any("document.xml" in item.root_path for item in ingested.materials)

    processor = ProcessMaterialService(session, store)
    for material in ingested.materials:
        processed = processor.process(material)
        session.flush()
        assert processed.material.status is MaterialStatus.READY


def test_process_go_project_cites_source_lines(
    session: Session,
    tmp_path: Path,
) -> None:
    project = make_go_project(tmp_path / "tools")
    ingested, store = _ingest(session, tmp_path, project)
    processed = ProcessMaterialService(session, store).process(ingested.materials[0])
    session.flush()

    assert processed.classification.material_type is MaterialType.PROJECT
    assert processed.classification.subtype == "go"
    assert processed.material.status is MaterialStatus.READY
    locations = {
        (unit.location.path, unit.location.line_start, unit.location.line_end)
        for unit in processed.research.content_units
    }
    assert ("main.go", 1, 5) in locations
    assert any(path == "go.mod" for path, _start, _end in locations)


def test_process_nested_dataset_and_installer_siblings_ready(
    session: Session,
    tmp_path: Path,
) -> None:
    root = make_nested_lab_data(tmp_path / "dump")
    (root / "paper.pdf").write_bytes(build_text_pdf(["Introduction"]))
    write_pe(root / "AndroidStudio-setup.exe")
    ingested, store = _ingest(session, tmp_path, root)
    by_path = {item.root_path: item for item in ingested.materials}
    assert "lab/data/" in by_path
    assert "paper.pdf" in by_path
    assert "AndroidStudio-setup.exe" in by_path

    processor = ProcessMaterialService(session, store)
    types: dict[str, MaterialType] = {}
    for material in ingested.materials:
        processed = processor.process(material)
        session.flush()
        assert processed.material.status is MaterialStatus.READY
        types[material.root_path] = processed.research.material_type
    assert types["lab/data/"] is MaterialType.DATASET
    assert types["paper.pdf"] is MaterialType.DOCUMENT


def test_process_caps_extracted_bytes(
    session: Session,
    tmp_path: Path,
) -> None:
    notes = tmp_path / "notes.txt"
    notes.write_text("abcdefghijklmnopqrstuvwxyz\n")
    ingested, store = _ingest(session, tmp_path, notes)
    processed = ProcessMaterialService(
        session, store, max_extract_bytes=8
    ).process(ingested.materials[0])
    session.flush()
    assert processed.material.status is MaterialStatus.READY
    assert processed.research.content_units[0].content == "abcdefgh"
