from pathlib import Path

from sqlalchemy.orm import Session

from material_platform.application.ingest_source import IngestSourceService
from material_platform.application.process_material import ProcessMaterialService
from material_platform.discovery.archive import ArchiveLimits
from material_platform.index import IndexService
from material_platform.infrastructure.object_store import FilesystemObjectStore
from material_platform.infrastructure.workspace import TemporaryWorkspace


def ingest_and_process(
    session: Session, tmp_path: Path, source: Path, index: IndexService
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
    ).ingest(source)
    session.flush()
    processor = ProcessMaterialService(session, store, index=index)
    for material in ingested.materials:
        processor.process(material)
    session.flush()
