from __future__ import annotations

import argparse
import sys
from pathlib import Path

from material_platform.application.deep_research import DeepResearchService
from material_platform.config import Settings
from material_platform.eval import (
    DEFAULT_SUITE,
    LEXICAL,
    format_report,
    lexical_failed,
    load_suite,
    score_suite,
)
from material_platform.index import make_index_service
from material_platform.infrastructure.database.engine import (
    make_engine,
    make_session_factory,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Score labeled retrieval queries against an indexed data dir."
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
    args = parser.parse_args(argv)
    if not args.cases.exists():
        print(f"cases not found: {args.cases}", file=sys.stderr)
        return 1

    settings = Settings()
    if not args.postgres:
        data_dir = (args.data_dir or settings.workspace_root).resolve()
        db_path = data_dir / "material.db"
        if not db_path.exists():
            print(f"database not found: {db_path}", file=sys.stderr)
            return 1
        settings = settings.model_copy(
            update={
                "database_url": f"sqlite:///{db_path}",
                "workspace_root": data_dir,
                "qdrant_url": None,
                "qdrant_path": data_dir / "qdrant",
            }
        )

    suite = load_suite(args.cases)
    modes = (LEXICAL,) if args.lexical_only else None
    engine = make_engine(settings)
    sessions = make_session_factory(engine)
    index = make_index_service(settings)
    with sessions() as session:
        score = score_suite(
            suite, DeepResearchService(session, index).select, modes=modes
        )
    print(format_report(score), end="")
    return 1 if lexical_failed(score) else 0
