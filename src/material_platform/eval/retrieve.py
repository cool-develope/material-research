from __future__ import annotations

import argparse
import sys
from pathlib import Path

from material_platform.application.local import sqlite_settings
from material_platform.config import Settings
from material_platform.eval import (
    DEFAULT_SUITE,
    format_report,
    lexical_failed,
    load_suite,
)
from material_platform.eval.experiment import (
    format_compare,
    parse_chunk_sweep,
    run_chunk_sweep,
    score_settings,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="mp eval",
        description="Score labeled retrieval queries, or sweep chunk_tokens.",
    )
    parser.add_argument(
        "--cases",
        type=Path,
        default=DEFAULT_SUITE,
        help="JSON suite (query → expected citations).",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help="Local data directory (sqlite under this path). "
        "Must match the directory used at ingest.",
    )
    parser.add_argument(
        "--postgres",
        action="store_true",
        help="Use DATABASE_URL and QDRANT_URL from the environment "
        "instead of local sqlite.",
    )
    parser.add_argument(
        "--lexical-only",
        action="store_true",
        help="Skip semantic cases (paraphrases that need BGE-M3).",
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=None,
        help="Zip or tree to ingest for a chunk_tokens sweep.",
    )
    parser.add_argument(
        "--sweep",
        default=None,
        help="Re-chunk and compare, e.g. chunk_tokens=256,512,1024.",
    )
    parser.add_argument(
        "--work-dir",
        type=Path,
        default=None,
        help="Parent directory for sweep data dirs (one per chunk size).",
    )
    args = parser.parse_args(argv)
    if not args.cases.exists():
        print(f"cases not found: {args.cases}", file=sys.stderr)
        return 1
    suite = load_suite(args.cases)
    settings = Settings()

    if args.sweep is not None:
        if args.postgres:
            print("sweep is sqlite-only", file=sys.stderr)
            return 1
        if args.source is None or not args.source.exists():
            print("sweep needs --source PATH", file=sys.stderr)
            return 1
        try:
            values = parse_chunk_sweep(args.sweep)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        work_dir = (args.work_dir or args.data_dir or settings.workspace_root).resolve()
        work_dir.mkdir(parents=True, exist_ok=True)
        runs = run_chunk_sweep(
            args.source.expanduser().resolve(),
            suite,
            values,
            work_dir=work_dir,
            settings=settings,
            lexical_only=args.lexical_only,
        )
        print(format_compare(runs), end="")
        for run in runs:
            print(format_report(run.score), end="")
        return 1 if any(lexical_failed(run.score) for run in runs) else 0

    if not args.postgres:
        data_dir = (args.data_dir or settings.workspace_root).resolve()
        db_path = data_dir / "material.db"
        if not db_path.exists():
            print(f"database not found: {db_path}", file=sys.stderr)
            return 1
        settings = sqlite_settings(settings, data_dir)

    score = score_settings(settings, suite, lexical_only=args.lexical_only)
    print(format_report(score), end="")
    return 1 if lexical_failed(score) else 0
