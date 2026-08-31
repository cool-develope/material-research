from __future__ import annotations

import argparse
import sys
from pathlib import Path

from material_platform.application.ingest_source import IngestSourceService
from material_platform.application.tree import format_ingest_report
from material_platform.config import Settings
from material_platform.discovery.archive import ArchiveLimits
from material_platform.infrastructure.database.engine import (
    make_engine,
    make_session_factory,
)
from material_platform.infrastructure.database.models import Base
from material_platform.infrastructure.object_store import FilesystemObjectStore
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
    args = parser.parse_args(argv)
    path = args.path.expanduser().resolve()
    if not path.exists():
        print(f"path not found: {path}", file=sys.stderr)
        return 1

    settings = Settings()
    data_dir = (args.data_dir or settings.workspace_root).resolve()
    data_dir.mkdir(parents=True, exist_ok=True)
    settings = settings.model_copy(
        update={"database_url": f"sqlite:///{data_dir / 'material.db'}"}
    )

    engine = make_engine(settings)
    Base.metadata.create_all(engine)
    sessions = make_session_factory(engine)
    store = FilesystemObjectStore(data_dir / "store")
    workspace = TemporaryWorkspace(data_dir)

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
        session.commit()

    sys.stdout.write(
        format_ingest_report(result.source, result.manifest, result.materials)
    )
    return 0
