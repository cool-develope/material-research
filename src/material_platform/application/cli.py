from __future__ import annotations

import argparse
import sys
from pathlib import Path

from material_platform.application.ingest_source import IngestSourceService
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
from material_platform.infrastructure.database.engine import (
    make_engine,
    make_session_factory,
)
from material_platform.infrastructure.database.models import Base
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
        help="Local data directory (sqlite + filesystem store).",
    )
    parser.add_argument(
        "--process",
        action="store_true",
        help="Classify, extract, and build ResearchMaterial for each Material.",
    )
    parser.add_argument(
        "--postgres",
        action="store_true",
        help="Use DATABASE_URL and MinIO from the environment instead of local sqlite.",
    )
    args = parser.parse_args(argv)
    path = args.path.expanduser().resolve()
    if not path.exists():
        print(f"path not found: {path}", file=sys.stderr)
        return 1

    settings = Settings()
    data_dir = (args.data_dir or settings.workspace_root).resolve()
    data_dir.mkdir(parents=True, exist_ok=True)
    if args.postgres:
        settings = settings.model_copy(update={"workspace_root": data_dir})
        store = make_object_store(settings)
    else:
        settings = settings.model_copy(
            update={"database_url": f"sqlite:///{data_dir / 'material.db'}"}
        )
        store = make_object_store(settings, filesystem_root=data_dir / "store")

    engine = make_engine(settings)
    if not args.postgres:
        Base.metadata.create_all(engine)
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
        if args.process:
            processor = ProcessMaterialService(
                session,
                store,
                pipeline_version=settings.pipeline_version,
                max_extract_bytes=settings.max_extract_bytes,
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
    if args.process:
        sys.stdout.write(format_process_report(result.manifest, processed))
    return 0
