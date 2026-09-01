from __future__ import annotations

import argparse
import sys
from pathlib import Path

from material_platform.application.deep_research import DeepResearchService
from material_platform.config import Settings
from material_platform.domain.citation import Citation
from material_platform.infrastructure.database.engine import (
    make_engine,
    make_session_factory,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Search indexed ResearchMaterials and print citations."
    )
    parser.add_argument("query")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help="Local data directory (sqlite under this path).",
    )
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument(
        "--postgres",
        action="store_true",
        help="Use DATABASE_URL from the environment instead of local sqlite.",
    )
    args = parser.parse_args(argv)

    settings = Settings()
    if not args.postgres:
        data_dir = (args.data_dir or settings.workspace_root).resolve()
        db_path = data_dir / "material.db"
        if not db_path.exists():
            print(f"database not found: {db_path}", file=sys.stderr)
            return 1
        settings = settings.model_copy(
            update={"database_url": f"sqlite:///{db_path}"}
        )

    engine = make_engine(settings)
    sessions = make_session_factory(engine)
    with sessions() as session:
        citations = DeepResearchService(session).select(
            args.query, limit=args.limit
        )
    return _print_citations(citations)


def _print_citations(citations: tuple[Citation, ...]) -> int:
    if not citations:
        print("No matching units.")
        return 0
    for index, citation in enumerate(citations, start=1):
        print(
            f"{index}. {citation.title}  {citation.citation}  "
            f"{citation.score:.2f}"
        )
        if citation.snippet:
            print(f"   {citation.snippet}")
        if citation.siblings:
            print(f"   also: {', '.join(citation.siblings)}")
    return 0
