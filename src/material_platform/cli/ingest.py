from __future__ import annotations

import argparse
import sys
from pathlib import Path

from material_platform.application.local import ingest_and_process, sqlite_settings
from material_platform.application.tree import (
    format_ingest_report,
    format_process_report,
)
from material_platform.config import Settings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="mp ingest",
        description="Discover materials in a file, directory, or ZIP.",
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
        settings = settings.model_copy(update={"workspace_root": data_dir})
    else:
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
