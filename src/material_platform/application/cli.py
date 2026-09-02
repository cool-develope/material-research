from __future__ import annotations

import argparse
import sys
from pathlib import Path

from material_platform.analysis import make_analyzer
from material_platform.application.ingest_source import IngestSourceService
from material_platform.application.local import ingest_and_process, sqlite_settings
from material_platform.application.process_material import (
    ProcessMaterialService,
    ProcessResult,
)
from material_platform.application.tree import (
    format_ingest_report,
    format_process_report,
)
from material_platform.config import Settings
from material_platform.discovery.archive import ArchiveLimits
from material_platform.index import make_index_service
from material_platform.infrastructure.database.engine import (
    make_engine,
    make_session_factory,
)
from material_platform.infrastructure.object_store import make_object_store
from material_platform.infrastructure.workspace import TemporaryWorkspace


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Discover materials in a file, directory, or ZIP."
    )
    parser.add_argument("path", type=Path)
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help="Local data directory (sqlite + filesystem store). "
        "Use a fresh directory per ingest so sources are not mixed.",
    )
    parser.add_argument(
        "--process",
        action="store_true",
        help="Classify, extract, and build ResearchMaterial for each Material.",
    )
    parser.add_argument(
        "--postgres",
        action="store_true",
        help="Use DATABASE_URL, MinIO, and QDRANT_URL from the environment "
        "instead of local sqlite.",
    )
    args = parser.parse_args(argv)
    path = args.path.expanduser().resolve()
    if not path.exists():
        print(f"path not found: {path}", file=sys.stderr)
        return 1

    settings = Settings()
    data_dir = (args.data_dir or settings.workspace_root).resolve()
    if args.postgres:
        return _postgres(path, settings, data_dir, process=args.process)
    settings = sqlite_settings(settings, data_dir)
    run = ingest_and_process(path, settings, process=args.process, strict=False)
    sys.stdout.write(
        format_ingest_report(
            run.ingest.source, run.ingest.manifest, run.ingest.materials
        )
    )
    if args.process:
        sys.stdout.write(format_process_report(run.ingest.manifest, run.processed))
    return 0


def _postgres(path: Path, settings: Settings, data_dir: Path, *, process: bool) -> int:
    settings = settings.model_copy(update={"workspace_root": data_dir})
    store = make_object_store(settings)
    engine = make_engine(settings)
    sessions = make_session_factory(engine)
    workspace = TemporaryWorkspace(data_dir)
    processed: tuple[ProcessResult, ...] = ()
    with sessions() as session:
        service = IngestSourceService.create(
            session,
            store,
            workspace,
            discovery_version=settings.discovery_version,
            max_archive_depth=settings.max_archive_depth,
            archive_limits=ArchiveLimits.from_settings(settings),
        )
        result = service.ingest(path)
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
            )
            items: list[ProcessResult] = []
            for material in result.materials:
                try:
                    items.append(processor.process(material))
                except Exception as exc:
                    print(
                        f"process failed for {material.root_path}: {exc}",
                        file=sys.stderr,
                    )
            processed = tuple(items)
        session.commit()
    sys.stdout.write(
        format_ingest_report(result.source, result.manifest, result.materials)
    )
    if process:
        sys.stdout.write(format_process_report(result.manifest, processed))
    return 0
