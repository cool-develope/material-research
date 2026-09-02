from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

from material_platform.application.ingest_source import (
    IngestResult,
    IngestSourceService,
)
from material_platform.application.process_material import ProcessResult
from material_platform.application.runtime import Runtime, uses_postgres
from material_platform.config import Settings

__all__ = [
    "LocalIngest",
    "ingest_and_process",
    "sqlite_settings",
    "uses_postgres",
]


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


def ingest_and_process(
    path: Path,
    settings: Settings,
    *,
    process: bool = True,
    strict: bool = True,
    progress: bool | None = None,
) -> LocalIngest:
    runtime = Runtime(settings)
    processed: tuple[ProcessResult, ...] = ()
    if progress is None:
        progress = sys.stderr.isatty()
    with runtime.session() as session:
        ingest = IngestSourceService.create(
            session,
            runtime.store,
            runtime.workspace,
            discovery_version=settings.discovery_version,
            max_archive_depth=settings.max_archive_depth,
            archive_limits=runtime.archive_limits(),
        ).ingest(path)
        if progress:
            print(
                f"discovered {len(ingest.materials)} materials",
                flush=True,
                file=sys.stderr,
            )
        if process:
            processor = runtime.processor(session)
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
    return LocalIngest(ingest=ingest, processed=processed)
