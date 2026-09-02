from __future__ import annotations

import argparse
import sys
from pathlib import Path

from material_platform.application.deep_research import DeepResearchService, MaterialHit
from material_platform.application.local import sqlite_settings
from material_platform.application.runtime import Runtime
from material_platform.config import Settings
from material_platform.index.service import SEARCH_PAGE_DEFAULT, SEARCH_PAGE_MAX


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="mp search",
        description="Search indexed materials and print a ranked list.",
    )
    parser.add_argument("query")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help="Local data directory (sqlite under this path). "
        "Must match the directory used at ingest.",
    )
    parser.add_argument("--page", type=int, default=1)
    parser.add_argument(
        "--page-size",
        type=int,
        default=SEARCH_PAGE_DEFAULT,
        help=f"Materials per page (1-{SEARCH_PAGE_MAX}).",
    )
    parser.add_argument(
        "--material-type",
        default=None,
        help="Restrict search to a material type (document, project, dataset, …).",
    )
    parser.add_argument(
        "--postgres",
        action="store_true",
        help="Use DATABASE_URL and QDRANT_URL from the environment "
        "instead of local sqlite.",
    )
    args = parser.parse_args(argv)
    if args.page < 1:
        print("page must be >= 1", file=sys.stderr)
        return 1
    if args.page_size < 1 or args.page_size > SEARCH_PAGE_MAX:
        print(f"page-size must be 1-{SEARCH_PAGE_MAX}", file=sys.stderr)
        return 1

    settings = Settings()
    if not args.postgres:
        data_dir = (args.data_dir or settings.workspace_root).resolve()
        db_path = data_dir / "material.db"
        if not db_path.exists():
            print(f"database not found: {db_path}", file=sys.stderr)
            return 1
        settings = sqlite_settings(settings, data_dir)

    runtime = Runtime(settings)
    offset = (args.page - 1) * args.page_size
    try:
        with runtime.session() as session:
            page = DeepResearchService(session, runtime.index).search(
                args.query,
                offset=offset,
                limit=args.page_size,
                material_type=args.material_type,
            )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return _print_page(
        page.results,
        has_more=page.has_more,
        page=args.page,
        page_size=args.page_size,
    )


def _print_page(
    results: tuple[MaterialHit, ...],
    *,
    has_more: bool,
    page: int,
    page_size: int,
) -> int:
    if not results:
        print("No matching materials.")
        return 0
    start = (page - 1) * page_size
    for index, hit in enumerate(results, start=start + 1):
        print(
            f"{index}. {hit.title}  {hit.material_type}  "
            f"{hit.root_path}  {hit.score:.2f}"
        )
        if hit.siblings:
            print(f"   also: {', '.join(hit.siblings)}")
    if has_more:
        print(f"   more: page {page + 1}")
    return 0
