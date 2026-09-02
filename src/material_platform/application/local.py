from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

from material_platform.analysis import make_analyzer
from material_platform.application.ingest_source import (
    IngestResult,
    IngestSourceService,
)
from material_platform.application.process_material import (
    ProcessMaterialService,
    ProcessResult,
)
from material_platform.config import Settings
from material_platform.discovery.archive import ArchiveLimits
from material_platform.index import make_index_service
from material_platform.infrastructure.database.engine import (
    make_engine,
    make_session_factory,
)
from material_platform.infrastructure.database.models import Base
from material_platform.infrastructure.object_store import make_object_store
from material_platform.infrastructure.workspace import TemporaryWorkspace


@dataclass(frozen=True)
class LocalIngest:
    ingest: IngestResult
    processed: tuple[ProcessResult, ...]

    @property
    def materials(self) -> int:
        return len(self.ingest.materials)

    @property
    def units(self) -> int:
        return sum(len(item.research.content_units) for item in self.processed)


def sqlite_settings(settings: Settings, data_dir: Path) -> Settings:
    data_dir = data_dir.resolve()
    data_dir.mkdir(parents=True, exist_ok=True)
    return settings.model_copy(
        update={
            "database_url": f"sqlite:///{data_dir / 'material.db'}",
            "workspace_root": data_dir,
            "qdrant_url": None,
            "qdrant_path": data_dir / "qdrant",
        }
    )


def uses_postgres(settings: Settings) -> bool:
    return settings.database_url.startswith("postgresql")


def ingest_and_process(
    path: Path,
    settings: Settings,
    *,
    process: bool = True,
    strict: bool = True,
    progress: bool | None = None,
) -> LocalIngest:
    data_dir = settings.workspace_root
    data_dir.mkdir(parents=True, exist_ok=True)
    postgres = uses_postgres(settings)
    store = (
        make_object_store(settings)
        if postgres
        else make_object_store(settings, filesystem_root=data_dir / "store")
    )
    engine = make_engine(settings)
    if not postgres:
        Base.metadata.create_all(engine)
    sessions = make_session_factory(engine)
    workspace = TemporaryWorkspace(data_dir)
    processed: tuple[ProcessResult, ...] = ()
    if progress is None:
        progress = sys.stderr.isatty()
    with sessions() as session:
        ingest = IngestSourceService.create(
            session,
            store,
            workspace,
            discovery_version=settings.discovery_version,
            max_archive_depth=settings.max_archive_depth,
            archive_limits=ArchiveLimits.from_settings(settings),
        ).ingest(path)
        if progress:
            print(
                f"discovered {len(ingest.materials)} materials",
                flush=True,
                file=sys.stderr,
            )
        if process:
            index = make_index_service(settings)
            processor = ProcessMaterialService(
                session,
                store,
                index,
                pipeline_version=settings.pipeline_version,
                max_extract_bytes=settings.max_extract_bytes,
                max_units_per_material=settings.max_units_per_material,
                chunk_tokens=settings.chunk_tokens,
                chunk_overlap_tokens=settings.chunk_overlap_tokens,
                analyzer=make_analyzer(settings),
                settings=settings,
            )
            items: list[ProcessResult] = []
            total = len(ingest.materials)
            for step, material in enumerate(ingest.materials, start=1):
                if progress:
                    print(
                        f"process {step}/{total} {material.root_path}",
                        flush=True,
                        file=sys.stderr,
                    )
                try:
                    items.append(processor.process(material))
                except Exception as exc:
                    if strict:
                        raise
                    print(
                        f"process failed for {material.root_path}: {exc}",
                        file=sys.stderr,
                    )
            processed = tuple(items)
        session.commit()
    return LocalIngest(ingest=ingest, processed=processed)
