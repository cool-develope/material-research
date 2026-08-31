from pathlib import Path

from sqlalchemy.orm import Session

from material_platform.application.ingest_source import IngestSourceService
from material_platform.application.queue import WorkQueue, pipeline_run_key
from material_platform.discovery.archive import ArchiveLimits
from material_platform.domain.enums import MaterialStatus, ProcessingRunStatus
from material_platform.infrastructure.database.repositories import (
    ProcessingRunRepository,
)
from material_platform.infrastructure.object_store import FilesystemObjectStore
from material_platform.infrastructure.workspace import TemporaryWorkspace
from tests.unit.discovery.trees import make_mixed_tree, zip_contents


def _ingest(session: Session, tmp_path: Path, source_path: Path) -> None:
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
    service.ingest(source_path)
    session.flush()


def test_claim_pending_moves_discovered_to_processing(
    session: Session,
    tmp_path: Path,
) -> None:
    mixed = make_mixed_tree(tmp_path / "mixed")
    archive = zip_contents(mixed, tmp_path / "research.zip")
    _ingest(session, tmp_path, archive)

    queue = WorkQueue(session, pipeline_version="process-v1")
    first = queue.claim_pending(limit=2)
    session.flush()

    assert len(first) == 2
    assert all(item.status is MaterialStatus.PROCESSING for item in first)
    run = ProcessingRunRepository(session).get_latest(first[0].material_id)
    assert run is not None
    assert run.status is ProcessingRunStatus.CLAIMED

    second = queue.claim_pending(limit=10)
    session.flush()
    assert len(second) == 1

    third = queue.claim_pending(limit=10)
    assert third == ()


def test_pipeline_run_key_includes_version() -> None:
    from uuid import UUID

    material_id = UUID("00000000-0000-0000-0000-000000000001")
    assert pipeline_run_key(material_id, "process-v1") == (
        "00000000-0000-0000-0000-000000000001:process-v1"
    )
