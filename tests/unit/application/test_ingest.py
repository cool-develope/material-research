from pathlib import Path

from sqlalchemy.orm import Session

from material_platform.application import (
    IngestResult,
    IngestSourceService,
    format_ingest_report,
)
from material_platform.discovery.archive import ArchiveLimits
from material_platform.domain.enums import MaterialType
from material_platform.infrastructure.object_store import (
    FilesystemObjectStore,
    material_content,
)
from material_platform.infrastructure.workspace import TemporaryWorkspace
from tests.unit.discovery.trees import make_mixed_tree, zip_contents


def _ingest(
    session: Session, tmp_path: Path, source_path: Path
) -> tuple[IngestResult, FilesystemObjectStore, TemporaryWorkspace]:
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
    return result, store, workspace


def test_ingest_mixed_zip_creates_three_materials(
    session: Session,
    tmp_path: Path,
) -> None:
    mixed = make_mixed_tree(tmp_path / "mixed")
    archive = zip_contents(mixed, tmp_path / "research.zip")
    result, store, _workspace = _ingest(session, tmp_path, archive)

    assert len(result.materials) == 3
    paths = sorted(item.root_path for item in result.materials)
    assert paths == ["backend/", "dataset/", "paper.pdf"]

    report = format_ingest_report(result.source, result.manifest, result.materials)
    assert "research.zip" in report
    assert "CONTAINER" in report
    assert "backend/" in report
    assert "project candidate" in report
    assert "document candidate" in report
    assert "dataset candidate" in report

    backend = next(item for item in result.materials if item.root_path == "backend/")
    assert backend.material_type is MaterialType.PROJECT
    assert store.exists(material_content(backend.material_id, "src/main.py"))
    assert store.exists(material_content(backend.material_id, "pyproject.toml"))
    scratch = tmp_path / "work" / "scratch"
    leftover = (
        [item for item in scratch.rglob("*") if item.is_file()]
        if scratch.exists()
        else []
    )
    assert leftover == []


def test_reingest_same_zip_does_not_duplicate_materials(
    session: Session,
    tmp_path: Path,
) -> None:
    mixed = make_mixed_tree(tmp_path / "mixed")
    archive = zip_contents(mixed, tmp_path / "research.zip")
    first, _, _ = _ingest(session, tmp_path, archive)
    second, _, _ = _ingest(session, tmp_path, archive)

    assert first.source.source_id == second.source.source_id
    assert {item.material_id for item in first.materials} == {
        item.material_id for item in second.materials
    }
    assert len(second.materials) == 3
